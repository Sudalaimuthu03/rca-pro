"""
Run: python scripts/seed_data.py
Creates a test user and a handful of sample incidents (no AI analysis —
that happens through the UI / the /analyze endpoint, which calls out to
the Hugging Face API and needs HF_API_TOKEN set).
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from werkzeug.security import generate_password_hash
from database.connection import init_db, execute_query

TEST_USER = {
    "name": "Test User",
    "email": "test@rcai.dev",
    "password": "TestPass123",
}

INCIDENTS = [
    {
        "title": "Payment service returning 500s",
        "error_log": "java.sql.SQLTransientConnectionException: connection pool exhausted, 150/150 connections in use, 45 requests waiting",
        "severity": "CRITICAL",
    },
    {
        "title": "Auth service memory climbing steadily",
        "error_log": "java.lang.OutOfMemoryError: Java heap space at AuthSessionCache.put(AuthSessionCache.java:88)",
        "severity": "HIGH",
    },
    {
        "title": "Checkout API gateway timeouts",
        "error_log": "upstream timed out (110: Connection timed out) while reading response header from upstream, gateway: checkout-api",
        "severity": "HIGH",
    },
    {
        "title": "Disk usage alert on order-worker-3",
        "error_log": "No space left on device: write failed for /var/log/order-worker/app.log, errno 28",
        "severity": "MEDIUM",
    },
]


def run():
    init_db()

    existing = execute_query("SELECT id FROM users WHERE email = %s", (TEST_USER["email"],), fetch="one")
    if existing:
        user_id = existing["id"]
        print(f"Test user already exists (id={user_id})")
    else:
        row = execute_query(
            "INSERT INTO users (name, email, password_hash) VALUES (%s,%s,%s) RETURNING id",
            (TEST_USER["name"], TEST_USER["email"], generate_password_hash(TEST_USER["password"])),
            fetch="one",
        )
        user_id = row["id"]
        print(f"Created test user: {TEST_USER['email']} / {TEST_USER['password']} (id={user_id})")

    # Bug 16 fixed: only insert incidents that don't already exist for this user
    existing_count = execute_query(
        "SELECT COUNT(*) AS n FROM incidents WHERE user_id = %s", (user_id,), fetch="one"
    )
    if existing_count and existing_count["n"] > 0:
        print(f"Incidents already seeded ({existing_count['n']} found) — skipping insert.")
        return

    for inc in INCIDENTS:
        execute_query(
            "INSERT INTO incidents (user_id, title, error_log, severity) VALUES (%s,%s,%s,%s)",
            (user_id, inc["title"], inc["error_log"], inc["severity"]),
        )
    print(f"Seeded {len(INCIDENTS)} incidents. Log in and hit 'Analyze' on one to test the AI flow.")


if __name__ == "__main__":
    run()
