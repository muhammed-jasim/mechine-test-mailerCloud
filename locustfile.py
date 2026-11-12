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

import os
import sys
import time
import random
import uuid
import threading
from pathlib import Path
from locust import task, events
from locust.contrib.fasthttp import FastHttpUser

TOTAL_TARGET_REQUESTS = 100000
UNIQUE_TARGET_REQUESTS = 80000
DUPLICATE_TARGET_REQUESTS = 20000

# Unique prefix per test run so 80,000 are brand new and 20,000 are exact duplicates
RUN_ID = os.environ.get('LOAD_RUN_ID', uuid.uuid4().hex[:6])

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
    PLAN_KEYS.append(f"k-{RUN_ID}-{i}")

for i in range(DUPLICATE_TARGET_REQUESTS):
    PLAN_KEYS.append(f"k-{RUN_ID}-{i}")

# Shuffle with fixed seed for realistic interleaved distribution
random.seed(1337)
random.shuffle(PLAN_KEYS)


class FastSubmissionUser(FastHttpUser):
    wait_time = lambda self: 0
    network_timeout = 15.0
    connection_timeout = 15.0
    max_retries = 3

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
            with self.client.post(
                "/api/submissions/",
                json=payload,
                name="POST /api/submissions/",
                catch_response=True
            ) as response:
                if response.status_code == 201:
                    response.success()
                    with _lock:
                        _stored_count += 1
                elif response.status_code == 200:
                    response.success()
                    with _lock:
                        _duplicates_reported += 1
                else:
                    response.failure(f"HTTP {response.status_code}")
                    with _lock:
                        _errors_count += 1

                with _lock:
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

    # Query actual database counts using pure Django ORM
    actual_db_submissions = 0
    actual_db_duplicates = 0
    try:
        import django
        backend_dir = str(Path(__file__).resolve().parent / 'backend')
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)

        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
        django.setup()

        from submissions.models import Submission, DuplicateLog
        actual_db_submissions = Submission.objects.count()
        actual_db_duplicates = DuplicateLog.objects.count()
    except Exception as e:
        actual_db_submissions = f"Error reading DB via ORM: {e}"

    print("\n" + "=" * 70)
    print("                 OFFICIAL LOCUST LOAD TEST REPORT                ")
    print("=" * 70)
    print(f" Total Requests Completed        : {total_completed:,}")
    print(f" Stored Submissions (HTTP 201)   : {_stored_count:,} (Expected: {UNIQUE_TARGET_REQUESTS:,})")
    print(f" Duplicate Requests (HTTP 200)   : {_duplicates_reported:,} (Expected: {DUPLICATE_TARGET_REQUESTS:,})")
    print(f" Errors Encountered              : {_errors_count:,}")
    print(f" Total Duration                  : {duration:.2f} seconds")
    print(f" Throughput (Requests / Second)  : {rps:.2f} RPS")
    print(f" Actual Submissions in DB (ORM)  : {actual_db_submissions:,}")
    print(f" Actual Duplicate Logs in DB(ORM): {actual_db_duplicates:,}")
    print("=" * 70)
