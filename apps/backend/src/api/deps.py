"""Live server context determines permissions, never a client supplied role."""
from fastapi import Cookie, HTTPException
from auth.sessions import read_session

def current_session(msa_session: str | None = Cookie(default=None)):
    session = read_session(msa_session)
    if session is None:
        raise HTTPException(401, "Phiên đăng nhập hết hạn hoặc chưa đăng nhập")
    return session

def require_permission(permission):
    def dependency(msa_session: str | None = Cookie(default=None)):
        session = current_session(msa_session)
        if permission not in session["contextPermissions"]:
            raise HTTPException(403, "Ngữ cảnh hiện tại không có quyền thực hiện thao tác này")
        return session
    return dependency

