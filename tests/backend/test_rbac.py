"""Real ORM/API integration, isolated databases only; no permission mocks."""
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
import os
import sqlite3
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from shared.auth.db import reset_connection, initialize, transaction, engine
from shared.auth.models import User, Role, UserRole, AuthSession, Permission, RolePermission, AuditEvent
from shared.auth.sessions import now, token_hash, audit
from shared.auth.types import identity_uuid
from shared.auth.passwords import hash_password, verify_password
from apps.backend.api.app import app

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


@pytest.mark.parametrize('body', [{}, {'actor': 'forged-actor', 'owner': 'forged-owner',
    'password': 'private-denial-body', 'medication': 'private-denial-medication'}])
def test_unlinked_core_account_is_denied_without_creating_identity(client, monkeypatch, body):
    from unittest.mock import MagicMock
    from apps.backend.api.routes import intake
    core_connection = MagicMock()
    core_connection.__enter__.return_value.execute.return_value.fetchone.return_value = None
    monkeypatch.setattr(intake.psycopg, 'connect', lambda *a, **k: core_connection)
    monkeypatch.setenv('CORE_DB_DSN', 'unit-test-unprovisioned-core')
    monkeypatch.setenv('CORE_REFERENCE_BUILD', '0' * 64)
    monkeypatch.delenv('CORE_USER_BINDINGS', raising=False)
    signed_in = login(client)
    assert signed_in.status_code == 200
    identity = signed_in.json()['account']['id']
    assert client.get('/api/v1/intake/capabilities').json()['persistent_intake'] is False
    assert client.post('/api/v1/intake/workflows', json=body).status_code == 403
    # Read through a new session/engine after the request has fully unwound.
    reset_connection()
    with transaction() as db:
        rows = db.scalars(select(AuditEvent).where(AuditEvent.action_code == 'intake.denied.core_link_missing')).all()
        assert len(rows) == 1
        assert rows[0].actor_user_id == rows[0].target_id == identity
        assert rows[0].target_type == 'account' and rows[0].success is False
        assert 'private-denial' not in str(vars(rows[0])) and 'forged-' not in str(vars(rows[0]))
    assert all(call.args[0].startswith('SELECT 1 FROM identity.users')
               for call in core_connection.__enter__.return_value.execute.call_args_list)


def test_audit_actor_labels_and_read_permissions_preserve_stored_events(client):
    assert client.get('/api/admin/audit').status_code == 401
    assert client.post('/api/auth/login', json={'email': 'unknown-audit@example.com', 'password': 'invalid'}).status_code == 401
    orphan = str(uuid4())
    with transaction() as db:
        audit(db, orphan, 'synthetic.missing_actor', target=orphan)
        # Even a recognized system event must not override a non-NULL actor ID.
        audit(db, orphan, 'account.created', target=orphan)
        audit(db, None, 'synthetic.unknown', target=orphan)
        audit(db, None, 'account.created', target=orphan)
        audit(db, None, 'account.created', target_type='unrecognized', target=orphan)
        db.flush()
        before = {e.event_id: (e.actor_user_id, e.action_code, e.target_type, e.target_id, e.success, e.occurred_at)
                  for e in db.scalars(select(AuditEvent))}
    admin(client)
    response = client.get('/api/admin/audit')
    assert response.status_code == 200
    events = response.json()['events']
    failed = next(e for e in events if e['actionCode'] == 'auth.login_failed')
    assert failed['actorUserId'] is None and failed['actorName'] == 'Chưa xác định' and failed['success'] is False
    system = next(e for e in events if e['actionCode'] == 'permission.introduced')
    assert system['actorUserId'] is None and system['actorName'] == 'Hệ thống'
    created = next(e for e in events if e['actionCode'] == 'account.created' and e['actorUserId'] is None and e['targetType'] == 'account')
    assert created['actorName'] == 'Hệ thống'
    signed_in = next(e for e in events if e['actionCode'] == 'auth.login')
    assert signed_in['actorName'] == client.get('/api/auth/me').json()['account']['fullName']
    assert all(e['actorName'] == f'Tài khoản {orphan}' for e in events if e['actorUserId'] == orphan)
    assert all(e['actorName'] == 'Chưa xác định' for e in events
               if e['actionCode'] == 'synthetic.unknown' or e['targetType'] == 'unrecognized')
    with transaction() as db:
        after = {e.event_id: (e.actor_user_id, e.action_code, e.target_type, e.target_id, e.success, e.occurred_at)
                 for e in db.scalars(select(AuditEvent))}
    assert all(after[key] == value for key, value in before.items())
    assert login(client).status_code == 200
    assert client.get('/api/admin/audit').status_code == 403


@pytest.mark.parametrize('bindings', ['[]', '{"u-patient": "invalid"}', '{"u-patient": 7}',
    '{"u-patient": "12345678-1234-5678-1234-567812345678", "other": "12345678-1234-5678-1234-567812345678"}'])
def test_invalid_or_merged_core_bindings_fail_closed(client, monkeypatch, bindings):
    monkeypatch.setenv('CORE_USER_BINDINGS', bindings)
    assert login(client).status_code == 200
    assert client.post('/api/v1/intake/workflows').status_code == 503

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
    assert "clinical.case_review" not in switched.json()["contextPermissions"]
    assert "catalog.review" in switched.json()["contextPermissions"]
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
    assert next(r for r in rows if r["id"] == identity_uuid("u-support"))["roles"] == ["technical_support"]
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

def test_expiration_and_account_lock(client, monkeypatch):
    admin(client)
    assert grant(client, expiresAt=(now()-timedelta(seconds=1)).isoformat()).status_code == 422
    assert grant(client, expiresAt="2030-01-01T00:00:00").status_code == 422
    assert grant(client, expiresAt=(now()+timedelta(hours=1)).isoformat()).status_code == 200
    # Let the recorded grant expire; its historical interval is immutable.
    from shared.auth import sessions
    future = now() + timedelta(hours=2)
    monkeypatch.setattr(sessions, 'now', lambda: future)
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
    assert client.get(f"/api/auth/accounts/{identity_uuid('u-patient')}").status_code == 200
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
        grant = db.scalar(select(UserRole).where(UserRole.user_id == 'legacy', UserRole.role_id == 1))
        assert grant.revoked_at is not None
        assert db.get(User, 'legacy').legacy_user_id == 'legacy'
    reset_connection()
