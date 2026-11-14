"""Real ORM/API integration, isolated databases only; no permission mocks."""
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
import os
import sqlite3
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from auth.db import reset_connection, initialize, transaction, engine
from auth.models import User, Role, UserRole, AuthSession, Permission, RolePermission
from auth.sessions import now, token_hash
from auth.passwords import hash_password, verify_password
from api.app import app

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.delenv("AUTH_DATABASE_URL", raising=False)
    monkeypatch.setenv("AUTH_DB_PATH", str(tmp_path / "identity.sqlite"))
    reset_connection()
    with TestClient(app, headers={"origin": "http://127.0.0.1:5173"}) as client:
        yield client
    reset_connection()

def login(client, name="mai", password="Mai-patient-2026"):
    return client.post("/api/auth/login", json={"email": f"{name}.demo@example.com", "password": password})

def admin(client):
    assert login(client, "ha", "Ha-admin-2026").status_code == 200

def grant(client, user="u-support", role="hcp", **extra):
    return client.post("/api/admin/role-grants", json={"userId": user, "roleCode": role, "granted": True, **extra})

def test_hashes_and_validation(client):
    hashed = hash_password("correct")
    assert hashed != "correct" and verify_password("correct", hashed)
    assert not verify_password("wrong", hashed)
    assert not verify_password("correct", "broken")
    assert login(client, "MAI").status_code == 200
    invalid = client.post("/api/auth/login", json={"email": "bad", "password": "secret-test"})
    assert invalid.status_code == 422 and "secret-test" not in invalid.text

def test_all_role_permission_matrix(client):
    for name, password, role, status in [
        ("mai", "Mai-patient-2026", "patient", 403),
        ("an", "An-hcp-2026", "hcp", 403),
        ("huy", "Huy-review-2026", "medical_reviewer", 403),
        ("khoa", "Khoa-support-2026", "technical_support", 403),
        ("ha", "Ha-admin-2026", "admin", 200)]:
        result = login(client, name, password)
        assert result.status_code == 200 and result.json()["activeContext"] == role
        assert client.get("/api/admin/accounts").status_code == status
        ocr = client.post("/api/v1/ocr/extractions", files={"file": ("x.txt", b"x", "text/plain")})
        assert ocr.status_code == (415 if role in ("patient", "hcp", "medical_reviewer") else 403)

def test_context_is_server_owned_and_persisted(client):
    result = login(client, "multi", "Multi-role-2026")
    assert result.json()["activeContext"] is None
    assert result.json()["contextPermissions"] == []
    assert len(client.get("/api/auth/contexts").json()["contexts"]) == 2
    assert client.post("/api/auth/switch-context", json={"context": "admin"}).status_code == 403
    switched = client.post("/api/auth/switch-context", json={"context": "medical_reviewer"})
    assert "catalog.edit" in switched.json()["contextPermissions"]
    reset_connection()
    assert client.get("/api/auth/me").json()["activeContext"] == "medical_reviewer"
    assert client.post("/api/auth/switch-context", json={"context": "hcp"}).status_code == 200
    assert "catalog.edit" not in client.get("/api/auth/me").json()["contextPermissions"]

def test_grant_revoke_and_restart_preserves_changes(client):
    admin(client)
    assert grant(client).status_code == 200
    assert client.delete("/api/admin/users/u-support/roles/hcp").status_code == 200
    reset_connection()
    rows = client.get("/api/admin/accounts").json()["accounts"]
    assert next(r for r in rows if r["id"] == "u-support")["roles"] == ["technical_support"]
    events = client.get("/api/admin/audit").json()["events"]
    assert {"role.grant", "role.revoke", "auth.login"} <= {e["actionCode"] for e in events}

def test_live_revocation_invalidates_active_role(client):
    admin(client)
    assert grant(client).status_code == 200
    other = TestClient(app, headers={"origin": "http://127.0.0.1:5173"})
    login(other, "khoa", "Khoa-support-2026")
    other.post("/api/auth/switch-context", json={"context": "hcp"})
    client.delete("/api/admin/users/u-support/roles/hcp")
    assert other.get("/api/auth/me").json()["activeContext"] == "technical_support"
    assert other.post("/api/v1/ocr/extractions", files={"file": ("x", b"x", "text/plain")}).status_code == 403
    client.delete("/api/admin/users/u-support/roles/technical_support")
    assert other.get("/api/auth/me").status_code == 401

def test_expiration_and_account_lock(client):
    admin(client)
    assert grant(client, expiresAt=(now()-timedelta(seconds=1)).isoformat()).status_code == 422
    assert grant(client, expiresAt="2030-01-01T00:00:00").status_code == 422
    assert grant(client, expiresAt=(now()+timedelta(hours=1)).isoformat()).status_code == 200
    with transaction() as db:
        role = db.scalar(select(Role).where(Role.role_code == "hcp"))
        db.get(UserRole, ("u-support", role.role_id)).expires_at = (now()-timedelta(seconds=1)).isoformat()
    assert login(client, "khoa", "Khoa-support-2026").json()["roles"] == ["technical_support"]
    with transaction() as db:
        db.get(User, "u-support").account_status = "locked"
    assert client.get("/api/auth/me").status_code == 401

def test_cookie_rotation_expiration_logout_and_owner(client):
    result = login(client)
    assert "HttpOnly" in result.headers["set-cookie"] and "SameSite=lax" in result.headers["set-cookie"]
    old = client.cookies.get("msa_session")
    login(client)
    with transaction() as db:
        assert db.get(AuthSession, token_hash(old)) is None
    assert client.get("/api/auth/accounts/u-patient").status_code == 200
    assert client.get("/api/auth/accounts/u-admin").status_code == 403
    token = client.cookies.get("msa_session")
    with transaction() as db:
        db.get(AuthSession, token_hash(token)).expires_at = (now()-timedelta(seconds=1)).isoformat()
    assert client.get("/api/auth/me").status_code == 401
    login(client)
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401

def test_privilege_escalation_catalog_and_last_admin(client):
    login(client)
    assert grant(client, "u-patient", "admin").status_code == 403
    admin(client)
    assert client.delete("/api/admin/users/u-admin/roles/admin").status_code == 409
    assert grant(client, "u-admin", "admin", expiresAt=(now()+timedelta(hours=1)).isoformat()).status_code == 409
    assert grant(client, "missing").status_code == 404
    assert grant(client, role="superadmin").status_code == 422
    assert len(client.get("/api/admin/roles").json()["roles"]) == 5
    assert client.get("/api/admin/permissions").json()["permissions"]
    assert client.post("/api/admin/role-grants", json={"userId":"u-patient", "roleCode":"hcp", "granted":True},
                       headers={"origin": "https://attacker.invalid"}).status_code == 403

def test_permissions_are_read_from_database(client):
    admin(client)
    with transaction() as db:
        role = db.scalar(select(Role).where(Role.role_code == "admin"))
        db.delete(db.get(RolePermission, (role.role_id, "admin.accounts")))
    assert client.get("/api/admin/accounts").status_code == 403

def test_legacy_migration_preserves_rows(tmp_path, monkeypatch):
    path = tmp_path / "legacy.sqlite"
    connection = sqlite3.connect(path)
    connection.executescript("""
    CREATE TABLE users(user_id TEXT PRIMARY KEY,email TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,full_name TEXT NOT NULL,account_status TEXT NOT NULL);
    CREATE TABLE roles(role_id INTEGER PRIMARY KEY,role_code TEXT UNIQUE NOT NULL,role_name TEXT NOT NULL);
    CREATE TABLE user_roles(user_id TEXT NOT NULL,role_id INTEGER NOT NULL,granted_at TEXT NOT NULL,expires_at TEXT,revoked_at TEXT,PRIMARY KEY(user_id,role_id));
    CREATE TABLE auth_sessions(token_hash TEXT PRIMARY KEY,user_id TEXT NOT NULL,expires_at TEXT NOT NULL);
    CREATE TABLE audit_events(event_id INTEGER PRIMARY KEY,actor_user_id TEXT,action_code TEXT NOT NULL,target_type TEXT NOT NULL,target_id TEXT NOT NULL,success INTEGER NOT NULL,occurred_at TEXT NOT NULL);
    INSERT INTO users VALUES('legacy','legacy@example.com','keep-this-hash','Keep Name','locked');
    INSERT INTO roles VALUES(1,'hcp','HCP');
    INSERT INTO user_roles VALUES('legacy',1,'2020-01-01T00:00:00+00:00',NULL,'2021-01-01T00:00:00+00:00');
    """)
    connection.close()
    monkeypatch.delenv("AUTH_DATABASE_URL", raising=False)
    monkeypatch.setenv("AUTH_DB_PATH", str(path))
    monkeypatch.setenv("AUTH_SEED_DEMO", "0")
    reset_connection()
    initialize()
    reset_connection()
    initialize()
    with transaction() as db:
        assert db.get(User,"legacy").password_hash == "keep-this-hash"
        assert db.get(UserRole,("legacy",1)).revoked_at is not None
    reset_connection()
