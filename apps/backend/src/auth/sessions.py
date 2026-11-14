"""Opaque, hashed, server-side sessions. Every request revalidates live grants."""
import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func
from auth.db import initialize, transaction
from auth.models import User, Role, UserRole, AuthSession, AuditEvent
from auth.passwords import hash_password, verify_password
from auth.rbac import permissions_for

COOKIE = "msa_session"
SESSION_HOURS = 12
_DUMMY_HASH = hash_password("not-an-account-password")

def now():
    return datetime.now(timezone.utc)

def timestamp():
    return now().isoformat()

def instant(value):
    parsed = datetime.fromisoformat(value)
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed

def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()

def audit(db, actor, action, target_type="account", target="", success=True):
    db.add(AuditEvent(actor_user_id=actor, action_code=action, target_type=target_type,
        target_id=target, success=int(success), occurred_at=timestamp()))

def grant_is_active(grant, moment):
    return (not grant.revoked_at and instant(grant.granted_at) <= moment
            and (not grant.expires_at or instant(grant.expires_at) > moment))

def open_roles(user_id, db):
    rows = db.execute(select(Role.role_code, UserRole).join(UserRole).where(
        UserRole.user_id == user_id).order_by(Role.role_id)).all()
    moment = now()
    return [code for code, grant in rows if grant_is_active(grant, moment)]

def public_account(user, roles, context, db):
    return {"account": {"id": user.user_id, "email": user.email, "fullName": user.full_name,
            "accountStatus": user.account_status}, "roles": roles,
            "permissions": permissions_for(roles, db), "activeContext": context,
            "contextPermissions": permissions_for([context], db) if context else []}

def login_session(email, password, old_token=None):
    initialize()
    with transaction() as db:
        user = db.scalar(select(User).where(func.lower(User.email) == email.strip().lower()))
        correct = verify_password(password, user.password_hash if user else _DUMMY_HASH)
        status = "invalid"
        roles = open_roles(user.user_id, db) if user and correct else []
        if user and correct:
            status = "locked" if user.account_status != "active" else "ok" if roles else "invalid"
        if status != "ok":
            audit(db, user.user_id if user else None, "auth.login_failed", success=False)
            return status, None, None
        if old_token:
            old = db.get(AuthSession, token_hash(old_token))
            if old:
                db.delete(old)
        token = secrets.token_urlsafe(32)
        context = roles[0] if len(roles) == 1 else None
        db.add(AuthSession(token_hash=token_hash(token), user_id=user.user_id,
            expires_at=(now()+timedelta(hours=SESSION_HOURS)).isoformat(), active_context=context))
        audit(db, user.user_id, "auth.login", target=user.user_id)
        return "ok", public_account(user, roles, context, db), token

def resolve_session(db, token):
    if not token:
        return None
    session = db.get(AuthSession, token_hash(token))
    if not session:
        return None
    user = db.get(User, session.user_id)
    roles = open_roles(session.user_id, db) if user else []
    if instant(session.expires_at) <= now() or not user or user.account_status != "active" or not roles:
        audit(db, session.user_id, "auth.session_invalidated", target=session.user_id)
        db.delete(session)
        return None
    if session.active_context not in roles:
        session.active_context = roles[0] if len(roles) == 1 else None
    return session, user, roles

def read_session(token):
    initialize()
    with transaction() as db:
        resolved = resolve_session(db, token)
        if not resolved:
            return None
        session, user, roles = resolved
        return public_account(user, roles, session.active_context, db)

def switch_context(token, context):
    initialize()
    with transaction() as db:
        resolved = resolve_session(db, token)
        if not resolved:
            return None
        session, user, roles = resolved
        if context not in roles:
            audit(db, user.user_id, "auth.context_denied", "role", context, False)
            return False
        session.active_context = context
        replacement = secrets.token_urlsafe(32)
        db.add(AuthSession(token_hash=token_hash(replacement), user_id=user.user_id,
                           expires_at=session.expires_at, active_context=context))
        db.delete(session)
        audit(db, user.user_id, "auth.context_changed", "role", context)
        return public_account(user, roles, context, db), replacement

def delete_session(token):
    initialize()
    with transaction() as db:
        session = db.get(AuthSession, token_hash(token)) if token else None
        if session:
            audit(db, session.user_id, "auth.logout", target=session.user_id)
            db.delete(session)

def require_owner(session, user_id):
    if session["account"]["id"] != user_id:
        raise PermissionError("Cross-account resource access")

