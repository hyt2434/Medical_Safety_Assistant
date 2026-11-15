"""Local-only adversarial checks: isolated SQLite, real API/dependencies/ORM."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from api.app import app
from auth.db import reset_connection, transaction
from auth.models import User, Role, RolePermission, UserRole, AuthSession, AuditEvent
from auth.sessions import token_hash, now

ORIGIN = "http://127.0.0.1:5173"
ACCOUNTS = [
    ("mai", "Mai-patient-2026", "patient", "u-patient"),
    ("an", "An-hcp-2026", "hcp", "u-hcp"),
    ("huy", "Huy-review-2026", "medical_reviewer", "u-reviewer"),
    ("khoa", "Khoa-support-2026", "technical_support", "u-support"),
    ("ha", "Ha-admin-2026", "admin", "u-admin"),
]
ADMIN_READS = ["status", "accounts", "users", "roles", "permissions", "audit"]

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTH_DATABASE_URL", "")
    monkeypatch.setenv("AUTH_DB_PATH", str(tmp_path / "security.sqlite"))
    monkeypatch.setenv("AUTH_SEED_DEMO", "1")
    monkeypatch.setenv("AUTH_ENV", "test")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "0")
    monkeypatch.setenv("AUTH_ALLOWED_ORIGINS", ORIGIN)
    reset_connection()
    with TestClient(app, headers={"origin": ORIGIN}) as c:
        yield c
    reset_connection()

def login(c, name="mai", password="Mai-patient-2026"):
    return c.post("/api/auth/login", json={"email": f"{name}.demo@example.com", "password": password})

def admin(c):
    assert login(c, "ha", "Ha-admin-2026").status_code == 200

def grant(c, user="u-support", role="hcp"):
    return c.post("/api/admin/role-grants", json={"userId": user, "roleCode": role, "granted": True})

def test_removed_permission_stays_removed_after_restart(client):
    admin(client)
    with transaction() as db:
        role = db.scalar(select(Role).where(Role.role_code == "admin"))
        db.delete(db.get(RolePermission, (role.role_id, "admin.accounts")))
    assert client.get("/api/admin/accounts").status_code == 403
    reset_connection()
    assert client.get("/api/admin/accounts").status_code == 403

def test_context_rotation_rejects_replayed_old_token(client):
    assert login(client, "multi", "Multi-role-2026").status_code == 200
    old = client.cookies.get("msa_session")
    result = client.post("/api/auth/switch-context", json={"context": "hcp"})
    assert result.status_code == 200
    assert client.cookies.get("msa_session") != old
    assert client.get("/api/auth/me", headers={"cookie": f"msa_session={old}"}).status_code == 401

def test_grant_cannot_upgrade_an_existing_stolen_session(client):
    login(client, "khoa", "Khoa-support-2026")
    old = client.cookies.get("msa_session")
    client.cookies.clear()
    admin(client)
    assert grant(client).status_code == 200
    assert client.get("/api/auth/me", headers={"cookie": f"msa_session={old}"}).status_code == 401

def test_login_throttle_persists_across_restart(client, monkeypatch):
    monkeypatch.setenv("AUTH_LOGIN_ACCOUNT_LIMIT", "3")
    for _ in range(3):
        assert login(client, password="wrong").status_code == 401
    reset_connection()
    response = login(client, password="wrong")
    assert response.status_code == 429 and int(response.headers["retry-after"]) > 0

def test_csrf_missing_origin_rejected_even_with_cookie(client):
    login(client)
    client.headers.pop("origin")
    assert client.post("/api/auth/logout").status_code == 403
    assert client.get("/api/auth/me").status_code == 200

@pytest.mark.parametrize("name,password,role,user", ACCOUNTS)
def test_full_endpoint_matrix(client, name, password, role, user):
    assert login(client, name, password).status_code == 200
    assert client.get("/api/auth/me").status_code == 200
    assert client.get("/api/auth/contexts").status_code == 200
    assert client.get(f"/api/auth/accounts/{user}").status_code == 200
    assert client.get("/api/auth/accounts/another-account").status_code == 403
    for path in ADMIN_READS:
        assert client.get(f"/api/admin/{path}").status_code == (200 if role == "admin" else 403), path
    for method, path, body in [
        ("POST", "/api/admin/role-grants", {"userId": "u-patient", "roleCode": "hcp", "granted": True}),
        ("POST", "/api/admin/users/u-patient/roles", {"roleCode": "hcp"}),
        ("DELETE", "/api/admin/users/u-patient/roles/hcp", None),
    ]:
        result = client.request(method, path, **({"json": body} if body else {}))
        assert result.status_code == (200 if role == "admin" else 403), path
    ocr = client.post("/api/v1/ocr/extractions", files={"file": ("invalid.txt", b"x", "text/plain")})
    assert ocr.status_code == (415 if role in ("patient", "hcp", "medical_reviewer") else 403)

def test_anonymous_and_forged_cookie_matrix(client):
    for cookie in (None, "admin", "' OR 1=1 --", "a" * 43):
        client.cookies.clear()
        if cookie:
            client.cookies.set("msa_session", cookie)
        for path in ["/api/auth/me", "/api/auth/contexts", "/api/auth/accounts/u-admin"] + [f"/api/admin/{x}" for x in ADMIN_READS]:
            assert client.get(path).status_code == 401, path
        assert grant(client).status_code == 401
        assert client.post("/api/admin/users/u-patient/roles", json={"roleCode": "admin"}).status_code == 401
        assert client.delete("/api/admin/users/u-patient/roles/admin").status_code == 401
        assert client.post("/api/auth/switch-context", json={"context": "admin"}).status_code == 401
        assert client.post("/api/v1/ocr/extractions", files={"file": ("x.txt", b"x", "text/plain")}).status_code == 401

def test_mass_assignment_sqli_and_idor(client):
    for email in ("missing@example.com", "'OR'1'='1'--@example.com", "mai.demo@example.com"):
        r = client.post("/api/auth/login", json={"email": email, "password": "wrong"})
        assert r.status_code == 401 and r.json()["detail"] == "Email hoặc mật khẩu không đúng"
    secret = "must-not-appear-in-errors"
    r = client.post("/api/auth/login", json={"email": "mai.demo@example.com", "password": secret, "roles": ["admin"]})
    assert r.status_code == 422 and secret not in r.text
    login(client)
    for identity in ("u-hcp", "u-support", "u-admin", "u-reviewer", "' OR 1=1 --"):
        assert client.get(f"/api/auth/accounts/{identity}").status_code == 403
    assert client.post("/api/auth/switch-context", json={"context": "admin"}).status_code == 403
    assert client.post("/api/auth/switch-context", json={"context": "patient", "permissions": ["admin.roles"]}).status_code == 422
    assert client.get("/api/admin/accounts?role=admin", headers={"X-Role": "admin"}).status_code == 403
    admin(client)
    r = client.post("/api/admin/users/u-patient/roles", json={"roleCode": "hcp", "userId": "u-admin"})
    assert r.status_code == 422

def test_cookie_attributes_no_secrets_and_replay(client, monkeypatch, caplog):
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "1")
    result = login(client)
    header = result.headers["set-cookie"].lower()
    assert all(x in header for x in ("httponly", "secure", "samesite=lax", "path=/", "max-age=43200"))
    assert "domain=" not in header
    token = result.cookies.get("msa_session")
    assert len(token) == 43
    assert token not in result.text and "password" not in result.text and "token_hash" not in result.text
    with transaction() as db:
        assert db.get(AuthSession, token_hash(token)) is not None
        assert db.get(AuthSession, token) is None
        assert "Mai-patient-2026" not in db.get(User, "u-patient").password_hash
    assert token not in caplog.text and "Mai-patient-2026" not in caplog.text
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "0")
    client.cookies.clear()
    client.cookies.set("msa_session", token)
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me", headers={"cookie": f"msa_session={token}"}).status_code == 401

def test_csrf_origin_referer_and_cors(client):
    login(client)
    for origin in ("null", "https://attacker.invalid", ORIGIN + ".attacker.invalid"):
        assert client.post("/api/auth/logout", headers={"origin": origin}).status_code == 403
    assert client.post("/api/auth/logout", headers={"sec-fetch-site": "cross-site"}).status_code == 403
    client.headers.pop("origin")
    assert client.post("/api/auth/logout", headers={"referer": "https://attacker.invalid/"}).status_code == 403
    assert client.post("/api/auth/logout", headers={"referer": ORIGIN + "/dashboard"}).status_code == 204
    for origin, expected in [(ORIGIN, 200), ("https://attacker.invalid", 400)]:
        r = client.options("/api/auth/login", headers={"origin": origin, "access-control-request-method": "POST"})
        assert r.status_code == expected
        assert (r.headers.get("access-control-allow-origin") == origin) == (expected == 200)

def test_fk_unique_and_transaction_rollback(client):
    with pytest.raises(IntegrityError):
        with transaction() as db:
            db.add(UserRole(user_id="missing", role_id=99999, granted_at=now().isoformat()))
    with pytest.raises(IntegrityError):
        with transaction() as db:
            db.add(User(user_id="duplicate", email="MAI.DEMO@EXAMPLE.COM", full_name="test", password_hash="not-a-real-password", account_status="active"))
    with transaction() as db:
        assert db.get(User, "duplicate") is None
    admin(client)
    with transaction() as db:
        before = len(db.scalars(select(AuditEvent)).all())
    assert grant(client, user="missing").status_code == 404
    with transaction() as db:
        assert len(db.scalars(select(AuditEvent)).all()) == before

def test_concurrent_grants_keep_one_row_and_last_admin(client):
    admin(client)
    token = client.cookies.get("msa_session")
    def do_grant(_):
        with TestClient(app, headers={"origin": ORIGIN, "cookie": f"msa_session={token}"}) as c:
            return grant(c).status_code
    with ThreadPoolExecutor(max_workers=3) as pool:
        assert list(pool.map(do_grant, range(3))) == [200, 200, 200]
    with transaction() as db:
        role = db.scalar(select(Role).where(Role.role_code == "hcp"))
        assert len(db.scalars(select(UserRole).where(UserRole.user_id == "u-support", UserRole.role_id == role.role_id)).all()) == 1
    assert client.delete("/api/admin/users/u-admin/roles/admin").status_code == 409

def test_no_union_and_live_permission_removal(client):
    login(client, "multi", "Multi-role-2026")
    assert client.post("/api/v1/ocr/extractions", files={"file": ("x.txt", b"x", "text/plain")}).status_code == 403
    client.post("/api/auth/switch-context", json={"context": "hcp"})
    assert "catalog.edit" not in client.get("/api/auth/me").json()["contextPermissions"]
    with transaction() as db:
        role = db.scalar(select(Role).where(Role.role_code == "hcp"))
        db.delete(db.get(RolePermission, (role.role_id, "intake.ocr")))
    assert client.post("/api/v1/ocr/extractions", files={"file": ("x.txt", b"x", "text/plain")}).status_code == 403

def test_expired_and_locked_sessions_stay_invalid(client):
    login(client)
    token = client.cookies.get("msa_session")
    with transaction() as db:
        db.get(AuthSession, token_hash(token)).expires_at = (now()-timedelta(seconds=1)).isoformat()
    assert client.get("/api/auth/me").status_code == 401
    login(client)
    with transaction() as db:
        db.get(User, "u-patient").account_status = "locked"
    assert client.get("/api/auth/me").status_code == 401
    with transaction() as db:
        db.get(User, "u-patient").account_status = "active"
    assert client.get("/api/auth/me").status_code == 401

def test_production_rejects_unsafe_config_and_existing_demo_users(client, monkeypatch):
    import settings
    monkeypatch.setenv("AUTH_ENV", "production")
    with pytest.raises(RuntimeError):
        settings.validate_security_config()
    monkeypatch.setenv("AUTH_SEED_DEMO", "0")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "1")
    with pytest.raises(RuntimeError):
        settings.validate_security_config()
    monkeypatch.setenv("AUTH_ALLOWED_ORIGINS", "https://medical.example.com")
    settings.validate_security_config()
    reset_connection()
    from auth.db import initialize
    with pytest.raises(RuntimeError, match="development accounts"):
        initialize()

def test_rate_limit_peer_cannot_be_bypassed_with_forwarded_headers(client, monkeypatch):
    monkeypatch.setenv("AUTH_LOGIN_IP_LIMIT", "2")
    for i in range(2):
        assert login(client, name=f"missing{i}", password="wrong").status_code == 401
    result = client.post("/api/auth/login", headers={"X-Forwarded-For": "203.0.113.42"},
                         json={"email": "another@example.com", "password": "wrong"})
    assert result.status_code == 429

def test_body_limit_precedes_json_and_multipart_parsing(client):
    assert client.post("/api/auth/login", content=b"x" * (16 * 1024 + 1),
                       headers={"content-type": "application/json"}).status_code == 413
    assert client.post("/api/v1/ocr/extractions", content=b"x" * (11 * 1024 * 1024 + 1),
                       headers={"content-type": "multipart/form-data; boundary=x"}).status_code == 413

def test_security_headers_on_denials(client):
    for response in (client.get("/api/auth/me"), client.post("/api/auth/logout", headers={"origin": "null"})):
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["x-content-type-options"] == "nosniff"
