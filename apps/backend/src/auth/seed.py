"""Idempotent development seeds: existing accounts/grants are never overwritten."""
from sqlalchemy import select, func
from auth.models import User, Role, Permission, RolePermission, UserRole
from auth.passwords import hash_password
from auth.rbac import PERMISSIONS_BY_ROLE
from auth.seed_accounts import _ACCOUNTS

NAMES = {"patient": "Người dùng", "hcp": "HCP", "medical_reviewer": "Phản biện dữ liệu",
         "admin": "Quản trị", "technical_support": "Hỗ trợ kỹ thuật"}

def seed_catalog(db):
    # Serialize bootstrap alongside grant mutations on PostgreSQL.
    if db.bind.dialect.name == "postgresql":
        db.connection().exec_driver_sql("SELECT pg_advisory_xact_lock(74031822)")
    for code, permissions in PERMISSIONS_BY_ROLE.items():
        role = db.scalar(select(Role).where(Role.role_code == code))
        new_role = role is None
        if role is None:
            role = Role(role_code=code, role_name=NAMES[code])
            db.add(role)
            db.flush()
        for permission in permissions:
            if db.get(Permission, permission) is None:
                db.add(Permission(code=permission, description=permission))
                db.flush()
            # Existing roles are authoritative: restart must not restore removed permissions.
            # Future catalog changes require an explicit reviewed migration.
            if new_role:
                db.add(RolePermission(role_id=role.role_id, permission_code=permission))
    db.flush()

def seed_accounts(db):
    from auth.sessions import timestamp
    for identity, email, password, name, status, roles in _ACCOUNTS:
        if db.scalar(select(User).where(func.lower(User.email) == email.lower())) is not None:
            continue
        db.add(User(user_id=identity, email=email, password_hash=hash_password(password),
                    full_name=name, account_status=status))
        db.flush()
        for code in roles:
            role = db.scalar(select(Role).where(Role.role_code == code))
            db.add(UserRole(user_id=identity, role_id=role.role_id, granted_at=timestamp()))

def seed():
    from auth.db import initialize
    initialize()

