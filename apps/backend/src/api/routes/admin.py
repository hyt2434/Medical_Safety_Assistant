"""Administrative catalog and grants, protected by server permissions."""
from datetime import datetime
from fastapi import APIRouter, Cookie, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from api.deps import require_permission
from api.routes.auth import RoleCode, RoleOut, AccountOut
from auth.directory import list_accounts, list_audit, list_permissions, set_role_grant
from auth.rbac import role_catalog
router = APIRouter(prefix="/api/admin", tags=["RBAC administration"])

class GrantOut(BaseModel):
    roleCode: RoleCode
    grantedAt: str
    expiresAt: str | None
    revokedAt: str | None

class AdminAccountOut(AccountOut):
    roles: list[RoleCode]
    permissions: list[str]
    grants: list[GrantOut]

class AccountsOut(BaseModel):
    accounts: list[AdminAccountOut]

class DirectoryOut(AccountsOut):
    roleCatalog: list[RoleOut]

class RolesOut(BaseModel):
    roles: list[RoleOut]

class PermissionOut(BaseModel):
    code: str
    description: str

class PermissionsOut(BaseModel):
    permissions: list[PermissionOut]

class AuditOut(BaseModel):
    id: int
    actorUserId: str | None
    actorName: str
    actionCode: str
    targetType: str
    targetId: str
    success: bool
    occurredAt: str

class EventsOut(BaseModel):
    events: list[AuditOut]

class StatusOut(BaseModel):
    ok: bool
    email: str

class RoleGrantBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    userId: str = Field(min_length=1, max_length=80)
    roleCode: RoleCode
    granted: bool
    expiresAt: datetime | None = None

class GrantBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    roleCode: RoleCode
    expiresAt: datetime | None = None

def change(token, user_id, code, granted, expiry=None):
    result = set_role_grant(token, user_id, code, granted, expiry)
    errors = {"unauthorized": (401, "Phiên đăng nhập hết hạn"), "forbidden": (403, "Không có quyền cấp role"),
        "missing": (404, "Không tìm thấy tài khoản"), "invalid": (400, "Role không hợp lệ"),
        "expiry": (422, "Thời hạn phải có múi giờ và nằm trong tương lai"),
        "last_admin": (409, "Không thể gỡ hoặc đặt hết hạn quyền quản trị của mình hay quản trị cuối cùng")}
    if result in errors:
        status, message = errors[result]
        raise HTTPException(status, message)
    return {"accounts": list_accounts()}

@router.get("/status", response_model=StatusOut)
def status(session=Depends(require_permission("admin.accounts"))):
    return {"ok": True, "email": session["account"]["email"]}

@router.get("/accounts", response_model=DirectoryOut)
@router.get("/users", response_model=DirectoryOut)
def accounts(_=Depends(require_permission("admin.accounts"))):
    return {"roleCatalog": role_catalog(), "accounts": list_accounts()}

@router.get("/roles", response_model=RolesOut)
def roles(_=Depends(require_permission("admin.roles"))):
    return {"roles": role_catalog()}

@router.get("/permissions", response_model=PermissionsOut)
def permissions(_=Depends(require_permission("admin.roles"))):
    return {"permissions": list_permissions()}

@router.post("/role-grants", response_model=AccountsOut)
def grants(body: RoleGrantBody, _=Depends(require_permission("admin.roles")), msa_session: str | None = Cookie(default=None)):
    return change(msa_session, body.userId, body.roleCode, body.granted, body.expiresAt)

@router.post("/users/{user_id}/roles", response_model=AccountsOut)
def grant(user_id: str, body: GrantBody, _=Depends(require_permission("admin.roles")), msa_session: str | None = Cookie(default=None)):
    return change(msa_session, user_id, body.roleCode, True, body.expiresAt)

@router.delete("/users/{user_id}/roles/{role_code}", response_model=AccountsOut)
def revoke(user_id: str, role_code: RoleCode, _=Depends(require_permission("admin.roles")), msa_session: str | None = Cookie(default=None)):
    return change(msa_session, user_id, role_code, False)

@router.get("/audit", response_model=EventsOut)
def audit(_=Depends(require_permission("admin.audit"))):
    return {"events": list_audit()}

