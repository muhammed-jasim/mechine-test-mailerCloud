#!/usr/bin/env python3
"""
Load Test Dataset Generator
===========================
Generates 100,000 requests worth of data directly into PostgreSQL:
- 80,000 unique submissions into 'submissions_submission'
- 20,000 duplicate interceptions into 'submissions_duplicatelog'
- Updates Flink 'submissions_hourlyaggregation' buckets
"""

import os
import time
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import execute_values

load_dotenv('backend/.env')

print("\n" + "=" * 65)
print("       HIGH-SPEED 100,000 LOAD TEST DATASET GENERATOR       ")
print("=" * 65)

conn = psycopg2.connect(
    dbname=os.environ.get('DB_NAME', 'form_analytics'),
    user=os.environ.get('DB_USER', 'jssim'),
    password=os.environ.get('DB_PASSWORD', 'postgres'),
    host=os.environ.get('DB_HOST', 'localhost'),
    port=os.environ.get('DB_PORT', '5432'),
)
c = conn.cursor()

start_time = time.time()
now = datetime.now(timezone.utc)

# 1. Insert 80,000 unique submissions
print("[*] Generating 80,000 unique submissions for 'loadtest-form'...")
sub_batch = []
for i in range(80000):
    hour_offset = (i % 12)
    minute_offset = (i % 60)
    second_offset = (i % 60)
    ts = now - timedelta(hours=hour_offset, minutes=minute_offset, seconds=second_offset)
    sub_batch.append((
        'loadtest-form',
        f'load-key-{i}',
        f'user-load-{i}@example.com',
        '{"source": "loadtest", "benchmark": true}',
        ts.strftime('%Y-%m-%d %H:%M:%S%z')
    ))

execute_values(
    c,
    """
    INSERT INTO submissions_submission (form_id, idempotency_key, email, data, created_at)
    VALUES %s
    ON CONFLICT (idempotency_key) DO NOTHING;
    """,
    sub_batch,
    page_size=5000
)
conn.commit()
print(f"[+] 80,000 unique submissions inserted in {time.time() - start_time:.2f}s")

# 2. Insert 20,000 duplicate logs
t2 = time.time()
print("[*] Generating 20,000 duplicate interception logs...")
c.execute("SELECT id, idempotency_key FROM submissions_submission WHERE form_id = 'loadtest-form' LIMIT 20000;")
orig_records = c.fetchall()

dup_batch = []
for orig_id, ikey in orig_records:
    detected_ts = now - timedelta(minutes=(orig_id % 360))
    dup_batch.append((
        orig_id,
        'loadtest-form',
        ikey,
        f'duplicate-{ikey}@bot.com',
        '{"resubmitted": true, "reason": "idempotency duplicate test"}',
        detected_ts.strftime('%Y-%m-%d %H:%M:%S%z')
    ))

execute_values(
    c,
    """
    INSERT INTO submissions_duplicatelog (original_submission_id, form_id, idempotency_key, attempted_email, attempted_data, detected_at)
    VALUES %s;
    """,
    dup_batch,
    page_size=5000
)
conn.commit()
print(f"[+] 20,000 duplicate interception logs inserted in {time.time() - t2:.2f}s")

# 3. Compute Hourly Aggregations
print("[*] Refreshing Flink hourly aggregations in PostgreSQL...")
c.execute("""
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

c.execute("SELECT COUNT(*) FROM submissions_submission;")
total_subs = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM submissions_duplicatelog;")
total_dups = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM submissions_hourlyaggregation;")
total_aggs = c.fetchone()[0]

print("=" * 65)
print(f" TOTAL STORED SUBMISSIONS       : {total_subs:,}")
print(f" TOTAL DUPLICATES INTERCEPTED   : {total_dups:,}")
print(f" TOTAL HOURLY AGGREGATION ROWS  : {total_aggs:,}")
print(f" TOTAL DURATION                 : {time.time() - start_time:.2f}s")
print("=" * 65 + "\n")
conn.close()
