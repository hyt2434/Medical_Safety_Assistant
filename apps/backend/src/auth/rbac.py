"""Catalog defaults are seeded once. Runtime decisions read persisted permissions."""
from sqlalchemy import select
from auth.models import Role, RolePermission

PERMISSIONS_BY_ROLE = {
    "patient": ("patient.workspace", "intake.ocr"),
    "hcp": ("clinical.case_review", "intake.ocr"),
    "medical_reviewer": ("clinical.case_review", "catalog.review", "catalog.edit", "intake.ocr"),
    "admin": ("staff.directory", "admin.accounts", "admin.roles", "admin.audit"),
    "technical_support": ("staff.directory", "operations.queue"),
}

def permissions_for(roles, db=None):
    if db is None:
        from auth.db import initialize, transaction
        initialize()
        with transaction() as connection:
            return permissions_for(roles, connection)
    return sorted(set(db.scalars(select(RolePermission.permission_code).join(Role).where(Role.role_code.in_(roles))).all()))

def allows(roles, permission):
    return permission in permissions_for(roles)

def role_catalog(db=None):
    if db is None:
        from auth.db import initialize, transaction
        initialize()
        with transaction() as connection:
            return role_catalog(connection)
    permissions = permission_map(db)
    return [{"code": r.role_code, "name": r.role_name, "permissions": permissions.get(r.role_code, [])}
            for r in db.scalars(select(Role).order_by(Role.role_id))]


def permission_map(db):
    """Read persisted mappings once for bulk catalog/directory operations."""
    result = {}
    for code, permission in db.execute(select(Role.role_code, RolePermission.permission_code).join(Role)):
        result.setdefault(code, []).append(permission)
    return {code: sorted(values) for code, values in result.items()}
