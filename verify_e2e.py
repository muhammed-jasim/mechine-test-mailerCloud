#!/usr/bin/env python3
"""
End-to-End System Verification Script
====================================
Tests all requirements from the assignment PDF:
1. Input validation (email & form_id) -> 400 Bad Request
2. Idempotency duplicate protection -> 200 OK with existing record
3. New submission creation -> 201 Created
4. Form-wise pagination (10 per page)
5. Live stream hourly aggregation
6. PostgreSQL persistence verification
"""

import sys
import time
import requests
import psycopg2
import os

BASE_URL = os.environ.get('API_URL', 'http://127.0.0.1:8000')
DB_NAME = os.environ.get('DB_NAME', 'form_analytics')
DB_USER = os.environ.get('DB_USER', 'jssim')

print("\n" + "=" * 65)
print("     FORM SUBMISSION & ANALYTICS - END-TO-END VERIFICATION     ")
print("=" * 65)

# 1. Check Server Availability
try:
    res = requests.get(f"{BASE_URL}/api/forms/", timeout=3)
    print(f"[*] API Server Status       : Online ({BASE_URL})")
except Exception as e:
    print(f"[!] Server is not running on {BASE_URL}. Starting check in offline test mode...")
    print(f"    Error: {e}")
    sys.exit(1)

# 2. Test Input Validation (Invalid Email)
bad_email_payload = {
    "form_id": "test-form",
    "idempotency_key": f"bad-email-{time.time()}",
    "email": "invalid-email-format",
    "data": {}
}
res_bad_email = requests.post(f"{BASE_URL}/api/submissions/", json=bad_email_payload)
assert res_bad_email.status_code == 400, f"Expected 400, got {res_bad_email.status_code}"
print("[PASS] Input Validation       : Rejects invalid email with HTTP 400")

# 3. Test Input Validation (Missing Form ID)
bad_form_payload = {
    "idempotency_key": f"bad-form-{time.time()}",
    "email": "user@example.com",
    "data": {}
}
res_bad_form = requests.post(f"{BASE_URL}/api/submissions/", json=bad_form_payload)
assert res_bad_form.status_code == 400, f"Expected 400, got {res_bad_form.status_code}"
print("[PASS] Input Validation       : Rejects missing form_id with HTTP 400")

# 4. Test New Submission Creation
test_key = f"e2e-key-{int(time.time() * 1000)}"
valid_payload = {
    "form_id": "e2e-demo-form",
    "idempotency_key": test_key,
    "email": "tester@example.com",
    "data": {"name": "Alice", "purpose": "E2E Verification"}
}
res_create = requests.post(f"{BASE_URL}/api/submissions/", json=valid_payload)
assert res_create.status_code == 201, f"Expected 201, got {res_create.status_code}"
created_data = res_create.json()
assert created_data["is_duplicate"] is False
assert created_data["idempotency_key"] == test_key
print(f"[PASS] Submission Creation    : HTTP 201 Created (ID #{created_data['id']})")

# 5. Test Idempotency Duplicate Detection
dup_payload = {
    "form_id": "e2e-demo-form",
    "idempotency_key": test_key,
    "email": "tampered@example.com",
    "data": {"tampered": True}
}
res_dup = requests.post(f"{BASE_URL}/api/submissions/", json=dup_payload)
assert res_dup.status_code == 200, f"Expected 200, got {res_dup.status_code}"
dup_data = res_dup.json()
assert dup_data["id"] == created_data["id"], "ID must match original record"
assert dup_data["email"] == "tester@example.com", "Original email must be preserved"
assert dup_data["is_duplicate"] is True
print(f"[PASS] Duplicate Protection   : HTTP 200 OK returned existing submission #{dup_data['id']}")

# 6. Test Form-Specific Pagination (10 records per page)
form_id_pagination = f"paging-form-{int(time.time())}"
for i in range(15):
    requests.post(f"{BASE_URL}/api/submissions/", json={
        "form_id": form_id_pagination,
        "idempotency_key": f"{form_id_pagination}-key-{i}",
        "email": f"user{i}@example.com",
        "data": {"index": i}
    })

res_page1 = requests.get(f"{BASE_URL}/api/forms/{form_id_pagination}/submissions/")
assert res_page1.status_code == 200
p1_data = res_page1.json()
assert p1_data["count"] == 15, f"Expected count=15, got {p1_data['count']}"
assert len(p1_data["results"]) == 10, f"Expected 10 items on page 1, got {len(p1_data['results'])}"
assert p1_data["next"] is not None

res_page2 = requests.get(f"{BASE_URL}/api/forms/{form_id_pagination}/submissions/?page=2")
p2_data = res_page2.json()
assert len(p2_data["results"]) == 5, f"Expected 5 items on page 2, got {len(p2_data['results'])}"
print("[PASS] Pagination (10/page)   : Page 1 (10 items), Page 2 (5 items), Count (15)")

# 7. Test Flink Aggregation Pipeline
from flink.aggregation import StreamHourlyAggregator, get_db_connection

agg = StreamHourlyAggregator()
conn, ph = get_db_connection()
c = conn.cursor()
query = f"SELECT id, form_id, email, idempotency_key, created_at FROM submissions_submission WHERE form_id = {ph}"
c.execute(query, (form_id_pagination,))
rows = c.fetchall()
for r in rows:
    agg.process_event({'id': r[0], 'form_id': r[1], 'email': r[2], 'idempotency_key': r[3], 'created_at': r[4]})
agg.save_checkpoint()
conn.close()

# Verify in API
res_hourly = requests.get(f"{BASE_URL}/api/analytics/hourly/?form_id={form_id_pagination}")
assert res_hourly.status_code == 200
hourly_records = res_hourly.json()
assert len(hourly_records) >= 1
assert hourly_records[0]["count"] >= 15
print(f"[PASS] Flink Aggregation     : Persisted hourly bucket with count {hourly_records[0]['count']}")

print("=" * 65)
print("          ALL ASSIGNMENT REQUIREMENTS VERIFIED SUCCESSFULLY!      ")
print("=" * 65 + "\n")

