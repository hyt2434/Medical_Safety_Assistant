"""Bulk reads must preserve live grant semantics without per-account queries."""
from datetime import timedelta
from sqlalchemy import event, select
import pytest
from auth.db import initialize, reset_connection, engine, transaction
from auth.directory import list_accounts
from auth.models import User, UserRole, Role, RolePermission
from auth.rbac import role_catalog
from auth.sessions import now


@pytest.fixture
def database(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTH_DATABASE_URL", "")
    monkeypatch.setenv("AUTH_DB_PATH", str(tmp_path / "architecture.sqlite"))
    monkeypatch.setenv("AUTH_ENV", "test")
    monkeypatch.setenv("AUTH_SEED_DEMO", "0")
    reset_connection()
    initialize()
    yield
    reset_connection()


def read_count(operation):
    statements = []
    def record(_conn, _cursor, statement, *_args):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)
    event.listen(engine(), "before_cursor_execute", record)
    try:
        result = operation()
    finally:
        event.remove(engine(), "before_cursor_execute", record)
    return result, len(statements)


@pytest.mark.parametrize("count", [1, 40])
def test_directory_bounded_queries_and_grant_semantics(database, count):
    moment = now()
    with transaction() as db:
        roles = {r.role_code: r.role_id for r in db.scalars(select(Role))}
        for i in range(count):
            user_id = f"architecture-{i}"
            db.add(User(user_id=user_id, email=f"{i}@example.test", full_name=user_id,
                        password_hash="unused", account_status="active"))
            db.flush()
            for code, expiry, revoked, granted in [
                ("patient", None, None, moment - timedelta(days=1)),
                ("hcp", moment - timedelta(seconds=1), None, moment - timedelta(days=1)),
                ("admin", None, moment, moment - timedelta(days=1)),
                ("medical_reviewer", None, None, moment + timedelta(days=1)),
            ]:
                db.add(UserRole(user_id=user_id, role_id=roles[code], granted_at=granted.isoformat(),
                                expires_at=expiry.isoformat() if expiry else None,
                                revoked_at=revoked.isoformat() if revoked else None))
        # Runtime catalog edits must override seed defaults in bulk reads too.
        db.delete(db.get(RolePermission, (roles["patient"], "intake.ocr")))
    accounts, queries = read_count(list_accounts)
    assert len(accounts) == count
    assert queries == 3
    for account in accounts:
        assert account["roles"] == ["patient"]
        assert account["permissions"] == ["patient.workspace"]
        assert len(account["grants"]) == 4


def test_catalog_keeps_roles_with_no_permissions(database):
    with transaction() as db:
        db.add(Role(role_code="empty_test_role", role_name="Empty"))
    roles, queries = read_count(role_catalog)
    assert queries == 2
    assert next(r for r in roles if r["code"] == "empty_test_role")["permissions"] == []
