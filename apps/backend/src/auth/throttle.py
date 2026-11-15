"""DB-backed fixed-window account and peer budgets, including successful attempts.

Uses the actual peer address, never untrusted forwarding headers. Deployments behind
a proxy also need a trusted ingress limiter; the shared proxy peer budget is intentional.
"""
import hashlib
import math
import os
from datetime import timedelta
from sqlalchemy import delete
from auth.db import initialize, transaction
from auth.models import LoginThrottle
from auth.sessions import now, instant

def login_retry_after(email, peer):
    initialize()
    moment = now()
    window = max(1, int(os.environ.get("AUTH_LOGIN_WINDOW_SECONDS", "300")))
    budgets = [("account:" + email.strip().lower(), max(1, int(os.environ.get("AUTH_LOGIN_ACCOUNT_LIMIT", "20")))),
               ("peer:" + peer, max(1, int(os.environ.get("AUTH_LOGIN_IP_LIMIT", "100"))))]
    with transaction() as db:
        if db.bind.dialect.name == "postgresql":
            db.connection().exec_driver_sql("SELECT pg_advisory_xact_lock(74031823)")
        db.execute(delete(LoginThrottle).where(LoginThrottle.expires_at <= moment.isoformat()))
        rows = []
        retry = 0
        for value, limit in budgets:
            key = hashlib.sha256(value.encode()).hexdigest()
            row = db.get(LoginThrottle, key)
            if row is None:
                row = LoginThrottle(key_hash=key, attempts=0, expires_at=(moment + timedelta(seconds=window)).isoformat())
                db.add(row)
            if row.attempts >= limit:
                retry = max(retry, math.ceil((instant(row.expires_at) - moment).total_seconds()))
            rows.append(row)
        if not retry:
            for row in rows:
                row.attempts += 1
        return retry
