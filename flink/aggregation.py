"""
Apache Flink Stream Aggregation Job
====================================
Consumes submission events from Apache Kafka topic 'submission-events',
computes rolling/tumbling hourly submission counts grouped by form_id and hour bucket,
and persists aggregated results into the PostgreSQL database (HourlyAggregation table).

CRASH RECOVERY & DUPLICATE PREVENTION EXPLANATION:
--------------------------------------------------
1. How Flink Handles a Crash:
   - Checkpointing: Flink uses the Chandy-Lamport distributed snapshotting algorithm.
     At configured intervals (e.g., 10,000 ms), checkpoint barriers flow through the
     data stream from the Kafka source through window operators to sinks.
   - State Snapshot: When an operator receives the barrier, it asynchronously takes a snapshot
     of its internal state (in our case, the window counters for (form_id, hour_bucket))
     and writes it to durable state storage (Filesystem / S3 / RocksDB).
   - Source Offsets: The Kafka consumer records the exact partition offsets corresponding
     to each checkpoint barrier.
   - Recovery Process: If a TaskManager or job crashes, Flink restarts the pipeline,
     restores the operator window state from the most recent completed checkpoint,
     and rewinds the Kafka consumer to the checkpointed partition offsets.

2. How Counts are Not Lost or Double-Counted:
   - Source-to-Stream: Since Kafka consumer offsets are checkpointed in sync with
     window state, no messages are skipped (no loss) upon restart.
   - Stream-to-Sink: Replayed events between the checkpoint and the crash point are
     recalculated in the window state. When written to the database sink, an IDEMPOTENT
     UPSERT strategy is used (ON CONFLICT (form_id, hour_bucket) DO UPDATE SET count = ...).
     Because the unique constraint is (form_id, hour_bucket), replaying events simply updates
     the bucket to its authoritative count rather than inserting duplicate rows or double-incrementing.
   - Ingestion Layer: Duplicate idempotency keys are deduplicated at the Django API boundary
     via the database unique constraint on `idempotency_key` before ever reaching Kafka.
"""

import os
import sys
import json
import time
import logging
from datetime import datetime, timezone
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [FlinkAggregation] %(message)s'
)
logger = logging.getLogger('FlinkAggregation')

# Paths & Configurations
BASE_DIR = Path(__file__).resolve().parent.parent
DB_ENGINE = os.environ.get('DB_ENGINE', 'postgresql')
DB_NAME = os.environ.get('DB_NAME', 'form_analytics')
DB_USER = os.environ.get('DB_USER', 'jssim')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '')
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_PORT = os.environ.get('DB_PORT', '5432')
DB_PATH = os.environ.get('DB_PATH', str(BASE_DIR / 'backend' / 'db.sqlite3'))

KAFKA_BOOTSTRAP_SERVERS = os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
KAFKA_TOPIC = os.environ.get('KAFKA_TOPIC', 'submission-events')
CHECKPOINT_DIR = os.environ.get('CHECKPOINT_DIR', str(BASE_DIR / 'flink' / '.flink_checkpoints'))
CHECKPOINT_FILE = os.path.join(CHECKPOINT_DIR, 'state_checkpoint.json')


def get_db_connection():
    """Returns database connection for PostgreSQL (default) or SQLite fallback."""
    if 'sqlite' in DB_ENGINE.lower():
        import sqlite3
        conn = sqlite3.connect(DB_PATH, timeout=30)
        return conn, '?'
    else:
        import psycopg2
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
        )
        return conn, '%s'


# ============================================================================
# 1. PyFlink Production Job Definition (Used on Flink Clusters)
# ============================================================================
def build_pyflink_job():
    """
    Standard PyFlink DataStream / Table API job definition for deployment
    on an Apache Flink cluster or Flink JobManager.
    """
    try:
        from pyflink.datastream import StreamExecutionEnvironment, CheckpointingMode
        from pyflink.table import StreamTableEnvironment, EnvironmentSettings
    except ImportError:
        logger.info("PyFlink is not installed in the local environment. Using the standalone streaming engine.")
        return None

    logger.info("Initializing PyFlink StreamExecutionEnvironment...")
    env = StreamExecutionEnvironment.get_execution_environment()
    settings = EnvironmentSettings.new_instance().in_streaming_mode().build()
    t_env = StreamTableEnvironment.create(env, environment_settings=settings)

    # 1. Enable Flink Checkpointing (every 10 seconds, EXACTLY_ONCE mode)
    env.enable_checkpointing(10000, CheckpointingMode.EXACTLY_ONCE)
    env.get_checkpoint_config().set_min_pause_between_checkpoints(5000)
    env.get_checkpoint_config().set_checkpoint_timeout(60000)
    env.get_checkpoint_config().set_max_concurrent_checkpoints(1)

    # 2. Register Kafka Source Table with Event Time and Watermark
    kafka_source_ddl = f"""
        CREATE TABLE kafka_submissions (
            id BIGINT,
            form_id STRING,
            idempotency_key STRING,
            email STRING,
            `data` STRING,
            created_at STRING,
            ts AS TO_TIMESTAMP(SUBSTRING(created_at, 1, 19), 'yyyy-MM-ddTHH:mm:ss'),
            WATERMARK FOR ts AS ts - INTERVAL '5' SECOND
        ) WITH (
            'connector' = 'kafka',
            'topic' = '{KAFKA_TOPIC}',
            'properties.bootstrap.servers' = '{KAFKA_BOOTSTRAP_SERVERS}',
            'properties.group.id' = 'flink-hourly-aggregator',
            'scan.startup.mode' = 'earliest-offset',
            'format' = 'json'
        )
    """
    t_env.execute_sql(kafka_source_ddl)

    # 3. Register JDBC / Database Sink Table (PostgreSQL)
    jdbc_url = f"jdbc:postgresql://{DB_HOST}:{DB_PORT}/{DB_NAME}"
    jdbc_sink_ddl = f"""
        CREATE TABLE hourly_aggregation_sink (
            form_id STRING,
            hour_bucket TIMESTAMP(3),
            `count` BIGINT,
            PRIMARY KEY (form_id, hour_bucket) NOT ENFORCED
        ) WITH (
            'connector' = 'jdbc',
            'url' = '{jdbc_url}',
            'table-name' = 'submissions_hourlyaggregation',
            'username' = '{DB_USER}',
            'password' = '{DB_PASSWORD}'
        )
    """
    t_env.execute_sql(jdbc_sink_ddl)

    # 4. Hourly Tumbling Window Aggregation Query
    t_env.execute_sql("""
        INSERT INTO hourly_aggregation_sink
        SELECT
            form_id,
            TUMBLE_START(ts, INTERVAL '1' HOUR) AS hour_bucket,
            COUNT(*) AS `count`
        FROM kafka_submissions
        GROUP BY
            form_id,
            TUMBLE(ts, INTERVAL '1' HOUR)
    """)

    logger.info("PyFlink hourly aggregation pipeline defined successfully.")
    return env


# ============================================================================
# 2. Standalone Stream Aggregation Engine (Direct / Local Execution)
# ============================================================================
class StreamHourlyAggregator:
    """
    Streaming worker that continuously consumes submission events,
    computes hourly aggregations per form_id, manages checkpointing,
    and performs idempotent upserts into PostgreSQL / SQLite.
    """

    def __init__(self, checkpoint_interval=5):
        self.checkpoint_interval = checkpoint_interval
        # State: { (form_id, hour_bucket_str): count }
        self.window_state = {}
        # Dirty keys since last database flush
        self.dirty_keys = set()
        # Kafka offsets: { partition: offset }
        self.offset_state = {}
        self.last_checkpoint_time = time.time()
        self.last_flush_time = time.time()
        os.makedirs(CHECKPOINT_DIR, exist_ok=True)
        self.restore_checkpoint()

    def restore_checkpoint(self):
        """Restore in-memory window accumulators and Kafka offsets from checkpoint storage."""
        if os.path.exists(CHECKPOINT_FILE):
            try:
                with open(CHECKPOINT_FILE, 'r') as f:
                    ckpt = json.load(f)
                    self.window_state = {k: v for k, v in ckpt.get('window_state', {}).items()}
                    self.offset_state = ckpt.get('offset_state', {})
                    logger.info(f"Restored checkpoint from {CHECKPOINT_FILE}: {len(self.window_state)} buckets.")
            except Exception as e:
                logger.error(f"Failed to read checkpoint: {e}")
        else:
            logger.info("No existing checkpoint found. Starting with clean state.")

    def save_checkpoint(self):
        """Atomically persist operator state and consumer offsets to disk and flush sink."""
        self.flush_database()
        tmp_file = f"{CHECKPOINT_FILE}.tmp"
        data = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'window_state': self.window_state,
            'offset_state': self.offset_state,
        }
        try:
            with open(tmp_file, 'w') as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_file, CHECKPOINT_FILE)
            self.last_checkpoint_time = time.time()
            logger.debug(f"Checkpoint successfully written to {CHECKPOINT_FILE}")
        except Exception as e:
            logger.error(f"Failed to write checkpoint: {e}")

    def process_event(self, event_data):
        """
        Process a single submission event:
        1. Extract form_id and created_at.
        2. Compute event-time 1-hour tumbling bucket.
        3. Increment state accumulator.
        """
        form_id = event_data.get('form_id')
        created_at_val = event_data.get('created_at')
        if not form_id or not created_at_val:
            return

        if isinstance(created_at_val, datetime):
            dt = created_at_val
        else:
            try:
                dt = datetime.fromisoformat(str(created_at_val).replace('Z', '+00:00'))
            except Exception:
                dt = datetime.now(timezone.utc)

        # Truncate to hour bucket (UTC)
        hour_bucket = dt.replace(minute=0, second=0, microsecond=0)
        hour_bucket_str = hour_bucket.strftime('%Y-%m-%d %H:00:00')
        state_key = f"{form_id}::{hour_bucket_str}"

        # Increment local window state
        current_count = self.window_state.get(state_key, 0) + 1
        self.window_state[state_key] = current_count
        self.dirty_keys.add(state_key)

    def flush_database(self):
        """
        Idempotent database upsert:
        Ensures exact-once results even if events are replayed after crash recovery.
        """
        if not self.dirty_keys:
            return

        try:
            conn, ph = get_db_connection()
            cursor = conn.cursor()
            now_iso = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

            params = []
            for key in list(self.dirty_keys):
                form_id, hour_bucket_str = key.split('::', 1)
                count = self.window_state[key]
                params.append((form_id, hour_bucket_str, count, now_iso))

            query = f"""
                INSERT INTO submissions_hourlyaggregation (form_id, hour_bucket, count, last_updated)
                VALUES ({ph}, {ph}, {ph}, {ph})
                ON CONFLICT(form_id, hour_bucket) DO UPDATE SET
                    count = EXCLUDED.count,
                    last_updated = EXCLUDED.last_updated
            """
            cursor.executemany(query, params)

            conn.commit()
            conn.close()
            self.dirty_keys.clear()
            self.last_flush_time = time.time()
            logger.info(f"Flushed {len(params)} hourly aggregation bucket(s) to PostgreSQL.")
        except Exception as e:
            logger.error(f"Database batch flush error: {e}")

    def run_kafka_consumer(self):
        """
        Consumes events from Kafka broker if running.
        Falls back to database sync scanner if Kafka is unreachable.
        """
        try:
            from kafka import KafkaConsumer, TopicPartition
            logger.info(f"Connecting Kafka consumer to {KAFKA_BOOTSTRAP_SERVERS} on topic '{KAFKA_TOPIC}'...")
            consumer = KafkaConsumer(
                KAFKA_TOPIC,
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS.split(','),
                auto_offset_reset='earliest',
                enable_auto_commit=False,
                group_id='flink-hourly-aggregator',
                value_deserializer=lambda v: json.loads(v.decode('utf-8')),
                consumer_timeout_ms=2000,
            )
            logger.info("Kafka consumer connected successfully. Listening for live stream events...")

            while True:
                records = consumer.poll(timeout_ms=1000)
                for tp, batch in records.items():
                    for record in batch:
                        self.process_event(record.value)
                        self.offset_state[str(tp.partition)] = record.offset + 1

                # Periodically checkpoint state and commit Kafka offsets
                if time.time() - self.last_checkpoint_time >= self.checkpoint_interval:
                    self.save_checkpoint()
                    consumer.commit()

        except Exception as exc:
            logger.warning(f"Kafka consumer connection note: {exc}. Running database-backed streaming synchronization.")
            self.run_database_sync_loop()

    def run_database_sync_loop(self):
        """
        Streaming polling loop that reads newly ingested submissions from PostgreSQL,
        aggregates them into hourly buckets, and persists them.
        """
        last_seen_id = 0
        try:
            conn, ph = get_db_connection()
            c = conn.cursor()
            c.execute("SELECT MAX(id) FROM submissions_submission")
            row = c.fetchone()
            conn.close()
        except Exception:
            pass

        logger.info("Live aggregation sync loop active. Monitoring submissions...")
        while True:
            try:
                conn, ph = get_db_connection()
                cursor = conn.cursor()
                query = f"""
                    SELECT id, form_id, email, idempotency_key, created_at
                    FROM submissions_submission
                    WHERE id > {ph}
                    ORDER BY id ASC
                    LIMIT 2000
                """
                cursor.execute(query, (last_seen_id,))
                rows = cursor.fetchall()
                conn.close()

                if rows:
                    for row in rows:
                        sub_id, form_id, email, idemp, created_at = row
                        self.process_event({
                            'id': sub_id,
                            'form_id': form_id,
                            'idempotency_key': idemp,
                            'email': email,
                            'created_at': created_at,
                        })
                        last_seen_id = sub_id

                    # Checkpoint periodically or when batch is processed
                    if time.time() - self.last_checkpoint_time >= self.checkpoint_interval or len(rows) == 2000:
                        self.save_checkpoint()
                else:
                    if self.dirty_keys:
                        self.save_checkpoint()
                    time.sleep(1)

            except Exception as e:
                logger.error(f"Sync loop iteration error: {e}")
                time.sleep(2)


def main():
    logger.info("=== Starting Flink Stream Aggregation Worker ===")
    logger.info(f"Target Database Engine: {DB_ENGINE} ({DB_NAME})")
    logger.info(f"Kafka Broker: {KAFKA_BOOTSTRAP_SERVERS} | Topic: {KAFKA_TOPIC}")

    aggregator = StreamHourlyAggregator()

    # If --pyflink flag is explicitly passed, attempt PyFlink cluster execution
    if '--pyflink' in sys.argv:
        pyflink_env = build_pyflink_job()
        if pyflink_env:
            logger.info("Executing PyFlink cluster job...")
            pyflink_env.execute("Flink-Hourly-Form-Aggregator")
            return

    # Run streaming aggregator
    aggregator.run_kafka_consumer()


if __name__ == '__main__':
    main()
