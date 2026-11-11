"""
Apache Flink Stream Aggregation Job
====================================
Consumes submission events and computes rolling/tumbling hourly submission counts
grouped by form_id and 1-hour time buckets, persisting results into PostgreSQL
(HourlyAggregation table).

CRASH RECOVERY & EXACTLY-ONCE EXPLANATION:
------------------------------------------
1. How the Stream Aggregation Job Handles a Crash:
   - Checkpointing (State Snapshotting):
     At regular intervals, the stream operator creates an atomic snapshot of:
       a) Operator window state: in-memory counts for each (form_id, hour_bucket).
       b) Stream source offsets: the exact `last_processed_id` (or Kafka partition offset).
     This snapshot is written atomically to durable storage (`.flink_checkpoints/state_checkpoint.json`).
   - Crash Event:
     If the worker process, container, or server crashes (SIGKILL, hardware failure, or power loss),
     in-flight in-memory state is terminated, but the persistent checkpoint remains untouched.
   - Recovery Process:
     Upon restart, `restore_checkpoint()` reads `state_checkpoint.json`:
       a) Restores all window count accumulators to their state at the last checkpoint.
       b) Rewinds the stream reader to `last_processed_id`.
       c) Resumes processing strictly from `id > last_processed_id`.

2. How Counts are NOT Lost:
   - Because the source offset is saved in lockstep with the window state:
     Any submissions received during or after the crash are strictly consumed when the worker resumes.
     Zero submissions are skipped.

3. How Counts are NOT Double-Counted:
   - Stream Ingestion: The stream reader queries `WHERE id > last_processed_id`. No prior events are re-counted.
   - Sink Upsert: When writing to PostgreSQL, an idempotent UPSERT query is used:
     `INSERT INTO submissions_hourlyaggregation ... ON CONFLICT (form_id, hour_bucket) DO UPDATE SET count = EXCLUDED.count`.
     Even if events between the last checkpoint and crash are re-evaluated, the database is overwritten
     with the operator's authoritative total count, never blindly incremented (`count = count + 1`).
   - Duplicate submissions at the API layer are intercepted by the `idempotency_key` unique constraint
     and logged to `DuplicateLog`, so duplicates never enter the aggregation stream.
"""

import os
import sys
import json
import time
import signal
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
DB_PASSWORD = os.environ.get('DB_PASSWORD', 'postgres')
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
        with conn.cursor() as cur:
            cur.execute("SET TIME ZONE 'UTC'")
        conn.commit()
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
    and performs idempotent upserts into PostgreSQL.
    """

    def __init__(self, checkpoint_interval=5):
        self.checkpoint_interval = checkpoint_interval
        # State: { "form_id::YYYY-MM-DD HH:00:00+00": count }
        self.window_state = {}
        # Set of dirty keys that have changed since last DB flush
        self.dirty_keys = set()
        # Stream source offset (PostgreSQL submission ID or Kafka offset)
        self.last_processed_id = 0
        # Kafka offsets: { partition_str: offset }
        self.offset_state = {}
        self.last_checkpoint_time = time.time()
        self.last_flush_time = time.time()
        self.is_running = True

        os.makedirs(CHECKPOINT_DIR, exist_ok=True)
        self.restore_checkpoint()

    def restore_checkpoint(self):
        """Restore in-memory window accumulators and stream offset from checkpoint storage."""
        if os.path.exists(CHECKPOINT_FILE):
            try:
                with open(CHECKPOINT_FILE, 'r') as f:
                    ckpt = json.load(f)
                    self.window_state = {k: v for k, v in ckpt.get('window_state', {}).items()}
                    self.offset_state = ckpt.get('offset_state', {})
                    self.last_processed_id = int(ckpt.get('last_processed_id', 0))
                    logger.info(
                        f"Restored checkpoint from {CHECKPOINT_FILE}: "
                        f"{len(self.window_state)} buckets, last_processed_id={self.last_processed_id}."
                    )
            except Exception as e:
                logger.error(f"Failed to read checkpoint: {e}")
                self.init_from_existing_data()
        else:
            logger.info("No existing checkpoint found. Initializing stream state from database.")
            self.init_from_existing_data()

    def init_from_existing_data(self):
        """
        If starting with no checkpoint, load existing state from PostgreSQL
        so we don't start from scratch or recount already-aggregated submissions.
        """
        try:
            conn, ph = get_db_connection()
            cur = conn.cursor()
            # 1. Load existing hourly aggregations into window_state
            cur.execute("SELECT form_id, hour_bucket, count FROM submissions_hourlyaggregation")
            loaded_count = 0
            for form_id, hour_bucket, count in cur.fetchall():
                if isinstance(hour_bucket, datetime):
                    bucket_str = hour_bucket.astimezone(timezone.utc).strftime('%Y-%m-%d %H:00:00+00')
                else:
                    bucket_str = str(hour_bucket)[:19] + '+00'
                state_key = f"{form_id}::{bucket_str}"
                self.window_state[state_key] = count
                loaded_count += 1

            # 2. Set last_processed_id to the current maximum submission id
            cur.execute("SELECT COALESCE(MAX(id), 0) FROM submissions_submission")
            row = cur.fetchone()
            self.last_processed_id = int(row[0]) if row and row[0] is not None else 0
            conn.close()

            logger.info(
                f"Initialized state from database: "
                f"{loaded_count} buckets loaded, last_processed_id={self.last_processed_id}."
            )
            # Write initial checkpoint
            self.save_checkpoint()
        except Exception as e:
            logger.error(f"Error initializing from database: {e}")

    def save_checkpoint(self):
        """Atomically persist operator state and consumer offsets to disk and flush sink."""
        self.flush_database()
        tmp_file = f"{CHECKPOINT_FILE}.tmp"
        data = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'last_processed_id': self.last_processed_id,
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

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)

        # Truncate to hour bucket (UTC)
        hour_bucket = dt.replace(minute=0, second=0, microsecond=0)
        hour_bucket_str = hour_bucket.strftime('%Y-%m-%d %H:00:00+00')
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
            now_iso = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S%z')

            params = []
            for key in list(self.dirty_keys):
                form_id, hour_bucket_str = key.split('::', 1)
                count = self.window_state[key]
                params.append((form_id, hour_bucket_str, count, now_iso))

            query = f"""
                INSERT INTO submissions_hourlyaggregation (form_id, hour_bucket, count, last_updated)
                VALUES ({ph}, {ph}, {ph}, {ph})
                ON CONFLICT (form_id, hour_bucket) DO UPDATE SET
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

    def run_stream_sync_loop(self, poll_interval=1.0, max_batches=None):
        """
        Continuously polls for newly inserted submissions,
        aggregates them into 1-hour tumbling windows, and updates PostgreSQL.
        """
        logger.info(f"Stream worker active. Listening for submissions where id > {self.last_processed_id}...")
        batches_processed = 0

        while self.is_running:
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
                cursor.execute(query, (self.last_processed_id,))
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
                        self.last_processed_id = max(self.last_processed_id, sub_id)

                    batches_processed += 1
                    # Save checkpoint and flush to database
                    self.save_checkpoint()
                    logger.info(
                        f"Processed {len(rows)} new submissions. "
                        f"Current last_processed_id={self.last_processed_id}. Checkpoint saved."
                    )
                else:
                    if self.dirty_keys:
                        self.save_checkpoint()
                    time.sleep(poll_interval)

                if max_batches and batches_processed >= max_batches:
                    break

            except Exception as e:
                logger.error(f"Stream loop error: {e}")
                time.sleep(poll_interval)

    def run_kafka_consumer(self):
        """
        Consumes events from Kafka broker if running.
        Falls back to database-backed streaming synchronization if Kafka is unreachable.
        """
        try:
            from kafka import KafkaConsumer
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

            while self.is_running:
                records = consumer.poll(timeout_ms=1000)
                for tp, batch in records.items():
                    for record in batch:
                        self.process_event(record.value)
                        self.offset_state[str(tp.partition)] = record.offset + 1

                if time.time() - self.last_checkpoint_time >= self.checkpoint_interval:
                    self.save_checkpoint()
                    consumer.commit()

        except Exception as exc:
            logger.info(f"Kafka broker offline/unavailable ({exc}). Using direct stream engine.")
            self.run_stream_sync_loop()

    def resync_all(self):
        """Recalculates all hourly aggregations from scratch from submissions_submission."""
        logger.info("Re-synchronizing all hourly aggregations from submissions...")
        conn, _ = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO submissions_hourlyaggregation (form_id, hour_bucket, count, last_updated)
            SELECT
                form_id,
                date_trunc('hour', created_at) AS hour_bucket,
                COUNT(*) AS count,
                NOW() AS last_updated
            FROM submissions_submission
            GROUP BY form_id, date_trunc('hour', created_at)
            ON CONFLICT (form_id, hour_bucket) DO UPDATE SET
                count = EXCLUDED.count,
                last_updated = EXCLUDED.last_updated;
        """)
        conn.commit()
        cur.execute("SELECT COALESCE(MAX(id), 0) FROM submissions_submission")
        self.last_processed_id = cur.fetchone()[0] or 0
        conn.close()

        # Re-populate local state
        self.window_state.clear()
        self.init_from_existing_data()
        logger.info(f"Resync complete. last_processed_id={self.last_processed_id}")


def print_status():
    """Prints current checkpoint and database status."""
    print("\n" + "=" * 60)
    print("      FLINK STREAM AGGREGATION & CHECKPOINT STATUS")
    print("=" * 60)
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, 'r') as f:
            data = json.load(f)
        print(f"Checkpoint File     : {CHECKPOINT_FILE}")
        print(f"Last Checkpoint     : {data.get('timestamp')}")
        print(f"Last Processed ID   : {data.get('last_processed_id')}")
        print(f"Tracked Windows     : {len(data.get('window_state', {}))}")
    else:
        print(f"Checkpoint File     : Not found ({CHECKPOINT_FILE})")

    try:
        conn, _ = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*), COALESCE(MAX(id), 0) FROM submissions_submission")
        sub_count, max_id = cur.fetchone()
        cur.execute("SELECT COUNT(*), COALESCE(SUM(count), 0) FROM submissions_hourlyaggregation")
        agg_rows, total_agg_count = cur.fetchone()
        conn.close()

        print("-" * 60)
        print(f"Total Submissions in DB   : {sub_count:,} (Max ID: {max_id:,})")
        print(f"Aggregated Rows in DB     : {agg_rows:,}")
        print(f"Sum of Aggregated Counts  : {total_agg_count:,}")
        print(f"Integrity Status          : {'MATCH (100% Exactly-Once)' if sub_count == total_agg_count else 'MISMATCH'}")
    except Exception as e:
        print(f"Database query error: {e}")
    print("=" * 60 + "\n")


def main():
    if '--status' in sys.argv:
        print_status()
        return

    aggregator = StreamHourlyAggregator()

    if '--resync' in sys.argv:
        aggregator.resync_all()
        print_status()
        return

    if '--pyflink' in sys.argv:
        pyflink_env = build_pyflink_job()
        if pyflink_env:
            logger.info("Executing PyFlink cluster job...")
            pyflink_env.execute("Flink-Hourly-Form-Aggregator")
            return

    # Handle graceful termination (Ctrl+C, SIGTERM)
    def handle_sigterm(signum, frame):
        logger.info(f"Signal {signum} received. Checkpointing state before shutdown...")
        aggregator.save_checkpoint()
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_sigterm)
    signal.signal(signal.SIGINT, handle_sigterm)

    # Run stream consumer
    aggregator.run_kafka_consumer()


if __name__ == '__main__':
    main()
