"""Cookie authentication and persistent context selection."""
import os
from typing import Literal
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from api.deps import current_session
from auth.sessions import COOKIE, SESSION_HOURS, login_session, read_session, delete_session, switch_context, require_owner
from auth.throttle import login_retry_after

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
RoleCode = Literal["patient", "hcp", "medical_reviewer", "technical_support", "admin"]

class LoginBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=1, max_length=1024)
    @field_validator("email")
    @classmethod
    def email_valid(cls, value):
        value = value.strip().lower()
        if "@" not in value or any(c.isspace() for c in value):
            raise ValueError("Email không hợp lệ")
        return value

class ContextBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    context: RoleCode

class AccountOut(BaseModel):
    id: str
    email: str
    fullName: str
    accountStatus: Literal["active", "locked"]

class SessionOut(BaseModel):
    account: AccountOut
    roles: list[RoleCode]
    permissions: list[str]
    activeContext: RoleCode | None
    contextPermissions: list[str]

class RoleOut(BaseModel):
    code: RoleCode
    name: str
    permissions: list[str]

class ContextsOut(BaseModel):
    activeContext: RoleCode | None
    contexts: list[RoleOut]

@router.post("/login", response_model=SessionOut)
def login(body: LoginBody, response: Response, request: Request, msa_session: str | None = Cookie(default=None)):
    retry = login_retry_after(body.email, request.client.host if request.client else "unknown")
    if retry:
        raise HTTPException(429, "Thử đăng nhập quá nhiều lần. Vui lòng thử lại sau.", headers={"Retry-After": str(retry)})
    status, account, token = login_session(body.email, body.password, msa_session)
    if status == "locked":
        raise HTTPException(403, "Tài khoản đang bị khóa")
    if status != "ok":
        raise HTTPException(401, "Email hoặc mật khẩu không đúng")
    set_session_cookie(response, token)
    return account

def set_session_cookie(response, token):
    response.set_cookie(COOKIE, token, httponly=True, samesite="lax",
        secure=os.environ.get("AUTH_COOKIE_SECURE", "0") == "1", path="/", max_age=SESSION_HOURS*3600)

@router.get("/me", response_model=SessionOut)
def me(session=Depends(current_session)):
    return session

@router.get("/contexts", response_model=ContextsOut)
def contexts(session=Depends(current_session)):
    from auth.rbac import role_catalog
    return {"activeContext": session["activeContext"],
            "contexts": [r for r in role_catalog() if r["code"] in session["roles"]]}

@router.post("/switch-context", response_model=SessionOut)
def change_context(body: ContextBody, response: Response, msa_session: str | None = Cookie(default=None)):
    result = switch_context(msa_session, body.context)
    if result is None:
        raise HTTPException(401, "Phiên đăng nhập hết hạn")
    if result is False:
        raise HTTPException(403, "Role đã bị thu hồi, hết hạn hoặc không được cấp")
    payload, token = result
    set_session_cookie(response, token)
    return payload

@router.get("/accounts/{user_id}", response_model=AccountOut)
def own_account(user_id: str, session=Depends(current_session)):
    try:
        require_owner(session, user_id)
    except PermissionError:
        raise HTTPException(403, "Không được truy cập tài khoản khác")
    return session["account"]

@router.post("/logout", status_code=204)
def logout(response: Response, msa_session: str | None = Cookie(default=None)):
    delete_session(msa_session)
    response.delete_cookie(COOKIE, path="/")

