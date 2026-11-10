"""
Locust Load Test Script
=======================
Generates:
- 100,000 total requests to POST /api/submissions/
- 80,000 unique submissions (unique idempotency keys)
- 20,000 duplicate requests (reusing idempotency keys)

Outputs the official report with:
- Stored submissions (201 Created)
- Duplicate submissions returned (200 OK)
- Errors encountered
- Requests per second (Throughput)
- Actual database row count verification
"""

import sys
import time
import random
import threading
import sqlite3
from pathlib import Path
from locust import task, events
from locust.contrib.fasthttp import FastHttpUser

TOTAL_TARGET_REQUESTS = 100000
UNIQUE_TARGET_REQUESTS = 80000
DUPLICATE_TARGET_REQUESTS = 20000

# Thread-safe synchronization
_lock = threading.Lock()
_dispatch_index = 0
_stored_count = 0
_duplicates_reported = 0
_errors_count = 0
_start_time = None
_end_time = None
_test_completed = False

# Build key pool deterministically:
# Exactly 80,000 distinct keys in total.
# 20,000 keys appear twice; 60,000 keys appear once.
# Total = 100,000 requests.
PLAN_KEYS = []
for i in range(UNIQUE_TARGET_REQUESTS):
    PLAN_KEYS.append(f"load-key-{i}")

for i in range(DUPLICATE_TARGET_REQUESTS):
    PLAN_KEYS.append(f"load-key-{i}")

# Shuffle with fixed seed for realistic interleaved distribution
random.seed(1337)
random.shuffle(PLAN_KEYS)


class FastSubmissionUser(FastHttpUser):
    wait_time = lambda self: 0

    @task
    def submit_form(self):
        global _dispatch_index, _stored_count, _duplicates_reported, _errors_count
        global _start_time, _end_time, _test_completed

        with _lock:
            if _test_completed:
                return

            if _start_time is None:
                _start_time = time.time()

            if _dispatch_index < TOTAL_TARGET_REQUESTS:
                key = PLAN_KEYS[_dispatch_index]
                _dispatch_index += 1
            else:
                key = None

        if key is None:
            with _lock:
                completed = _stored_count + _duplicates_reported + _errors_count
                if completed >= TOTAL_TARGET_REQUESTS and not _test_completed:
                    _test_completed = True
                    _end_time = time.time()
                    print("\n[Target Reached] All 100,000 requests processed. Stopping runner...")
                    self.environment.runner.quit()
            time.sleep(0.05)
            return

        payload = {
            "form_id": "loadtest-form",
            "idempotency_key": key,
            "email": f"user-{key}@example.com",
            "data": {
                "source": "locust_loadtest",
                "key": key
            }
        }

        try:
            response = self.client.post(
                "/api/submissions/",
                json=payload,
                name="POST /api/submissions/"
            )
            with _lock:
                if response.status_code == 201:
                    _stored_count += 1
                elif response.status_code == 200:
                    _duplicates_reported += 1
                else:
                    _errors_count += 1

                completed = _stored_count + _duplicates_reported + _errors_count
                if completed % 10000 == 0:
                    elapsed = time.time() - _start_time
                    current_rps = completed / max(elapsed, 0.001)
                    print(f"  Progress: {completed:,} / {TOTAL_TARGET_REQUESTS:,} requests ({current_rps:.1f} RPS)")

                if completed >= TOTAL_TARGET_REQUESTS and not _test_completed:
                    _test_completed = True
                    _end_time = time.time()
                    print("\n[Target Reached] All 100,000 requests completed. Stopping runner...")
                    self.environment.runner.quit()
        except Exception:
            with _lock:
                _errors_count += 1
                completed = _stored_count + _duplicates_reported + _errors_count
                if completed >= TOTAL_TARGET_REQUESTS and not _test_completed:
                    _test_completed = True
                    _end_time = time.time()
                    self.environment.runner.quit()


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    global _end_time
    if _end_time is None:
        _end_time = time.time()

    duration = max(_end_time - (_start_time or _end_time), 0.001)
    total_completed = _stored_count + _duplicates_reported + _errors_count
    rps = total_completed / duration

    # Query the actual database row count directly from PostgreSQL (or SQLite)
    actual_db_submissions = 0
    try:
        import os
        import psycopg2
        conn = psycopg2.connect(
            dbname=os.environ.get('DB_NAME', 'form_analytics'),
            user=os.environ.get('DB_USER', 'jssim'),
            password=os.environ.get('DB_PASSWORD', ''),
            host=os.environ.get('DB_HOST', 'localhost'),
            port=os.environ.get('DB_PORT', '5432'),
        )
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM submissions_submission")
        actual_db_submissions = c.fetchone()[0]
        conn.close()
    except Exception:
        try:
            import sqlite3
            db_path = Path(__file__).resolve().parent / 'backend' / 'db.sqlite3'
            conn = sqlite3.connect(str(db_path))
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM submissions_submission")
            actual_db_submissions = c.fetchone()[0]
            conn.close()
        except Exception as e:
            actual_db_submissions = f"Error reading DB: {e}"

    print("\n" + "=" * 70)
    print("                 OFFICIAL LOCUST LOAD TEST REPORT                ")
    print("=" * 70)
    print(f" Total Requests Completed        : {total_completed:,}")
    print(f" Stored Submissions (HTTP 201)   : {_stored_count:,} (Expected: {UNIQUE_TARGET_REQUESTS:,})")
    print(f" Duplicate Requests (HTTP 200)   : {_duplicates_reported:,} (Expected: {DUPLICATE_TARGET_REQUESTS:,})")
    print(f" Errors Encountered              : {_errors_count:,}")
    print(f" Total Duration                  : {duration:.2f} seconds")
    print(f" Throughput (Requests / Second)  : {rps:.2f} RPS")
    print(f" Actual Submissions in Database  : {actual_db_submissions:,}")
    print("=" * 70)
