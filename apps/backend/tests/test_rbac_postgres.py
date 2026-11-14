"""Opt-in checks against a dedicated loopback test DB; never drops/truncates tables."""
import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.engine import make_url
from auth.db import reset_connection, initialize, transaction
from auth.models import User, Role, UserRole
from auth.passwords import hash_password
from auth.sessions import timestamp
from api.app import app

@pytest.mark.skipif(not os.environ.get("RBAC_POSTGRES_TEST_URL"), reason="Set dedicated RBAC_POSTGRES_TEST_URL")
def test_postgres_migration_sessions_and_concurrent_grants(monkeypatch):
    url = os.environ["RBAC_POSTGRES_TEST_URL"]
    parsed = make_url(url)
    assert parsed.host in ("127.0.0.1", "localhost") and parsed.database.startswith("msa_auth_test_")
    monkeypatch.setenv("AUTH_DATABASE_URL", url)
    monkeypatch.setenv("AUTH_SEED_DEMO", "1")
    reset_connection()
    initialize()
    identity = "pg-" + uuid4().hex
    with transaction() as db:
        db.add(User(user_id=identity, email=f"{identity}@example.com", password_hash=hash_password("Pg-test-2026"), full_name="Postgres integration", account_status="active"))
        db.flush()
        role = db.scalar(select(Role).where(Role.role_code == "patient"))
        db.add(UserRole(user_id=identity, role_id=role.role_id, granted_at=timestamp()))
    with TestClient(app, headers={"origin": "http://127.0.0.1:5173"}) as client:
        assert client.post("/api/auth/login", json={"email":"ha.demo@example.com","password":"Ha-admin-2026"}).status_code == 200
        token = client.cookies.get("msa_session")
        def grant():
            with TestClient(app, headers={"origin": "http://127.0.0.1:5173"}) as parallel:
                parallel.cookies.set("msa_session", token)
                return parallel.post("/api/admin/role-grants", json={"userId":identity,"roleCode":"hcp","granted":True}).status_code
        with ThreadPoolExecutor(max_workers=3) as workers:
            assert list(workers.map(lambda _: grant(), range(3))) == [200,200,200]
        rows = client.get("/api/admin/accounts").json()["accounts"]
        assert next(r for r in rows if r["id"] == identity)["roles"].count("hcp") == 1
        assert client.delete(f"/api/admin/users/{identity}/roles/hcp").status_code == 200
        reset_connection()
        assert client.get("/api/admin/accounts").status_code == 200
        result = client.post("/api/auth/login", json={"email":f"{identity}@example.com","password":"Pg-test-2026"})
        assert result.json()["roles"] == ["patient"]
        assert client.get("/api/admin/accounts").status_code == 403
        client.post("/api/auth/logout")
        assert client.get("/api/auth/me").status_code == 401
    reset_connection()
