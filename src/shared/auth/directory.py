"""Admin operations revalidate the actor inside the write transaction."""
from sqlalchemy import select, delete, or_
from uuid import UUID
from shared.auth.db import initialize, transaction
from shared.auth.models import User, Role, Permission, UserRole, AuditEvent, AuthSession
from shared.auth.rbac import permissions_for, permission_map
from shared.auth.sessions import audit, open_roles, now, instant, timestamp, resolve_session, grant_is_active


def _iso(value):
    return instant(value).isoformat() if value is not None else None

def list_accounts():
    initialize()
    with transaction() as db:
        users = db.scalars(select(User).order_by(User.full_name)).all()
        grants_by_user = {}
        for code, grant in db.execute(select(Role.role_code, UserRole).join(UserRole).order_by(Role.role_id)):
            grants_by_user.setdefault(grant.user_id, []).append((code, grant))
        permissions = permission_map(db)
        moment = now()
        result = []
        for user in users:
            grants = grants_by_user.get(user.user_id, [])
            roles = [code for code, grant in grants if grant_is_active(grant, moment)]
            result.append({"id": user.user_id, "email": user.email, "fullName": user.full_name,
                "accountStatus": user.account_status, "roles": roles,
                "permissions": sorted({p for code in roles for p in permissions.get(code, [])}),
                "grants": [{"id": g.grant_id, "roleCode": code, "grantedAt": _iso(g.granted_at), "expiresAt": _iso(g.expires_at),
                            "revokedAt": _iso(g.revoked_at)} for code, g in grants]})
        return result

def _audit_actor_name(event, name):
    if name and name.strip():
        return name
    if event.actor_user_id is not None:
        return f"Tài khoản {event.actor_user_id}"
    # These existing events are emitted by server account provisioning and the
    # permission migration, respectively. NULL alone does not identify a system.
    if (event.action_code, event.target_type) in {
        ('account.created', 'account'), ('permission.introduced', 'permission')
    }:
        return "Hệ thống"
    return "Chưa xác định"


def list_audit():
    initialize()
    with transaction() as db:
        rows = db.execute(select(AuditEvent, User.full_name).outerjoin(User, User.user_id == AuditEvent.actor_user_id)
                          .order_by(AuditEvent.event_id.desc()).limit(500)).all()
        return [{"id": e.event_id, "actorUserId": e.actor_user_id, "actorName": _audit_actor_name(e, name),
            "actionCode": e.action_code, "targetType": e.target_type, "targetId": e.target_id,
            "success": bool(e.success), "occurredAt": _iso(e.occurred_at)} for e, name in rows]

def list_permissions():
    with transaction() as db:
        return [{"code": p.code, "description": p.description} for p in db.scalars(select(Permission).order_by(Permission.code))]

def set_role_grant(token, user_id, role_code, granted, expires_at=None):
    initialize()
    with transaction() as db:
        # SQLite BEGIN IMMEDIATE and PostgreSQL shared advisory lock serialize all grants.
        if db.bind.dialect.name == "postgresql":
            db.connection().exec_driver_sql("SELECT pg_advisory_xact_lock(74031822)")
        resolved = resolve_session(db, token)
        if not resolved:
            return "unauthorized"
        session, actor, roles = resolved
        if "admin.roles" not in permissions_for([session.active_context] if session.active_context else [], db):
            audit(db, actor.user_id, "role.denied", "user_role", f"{user_id}:{role_code}", False)
            return "forbidden"
        try:
            canonical = str(UUID(user_id))
        except ValueError:
            canonical = None
        user = db.get(User, canonical) if canonical else None
        if user is None:
            user = db.scalar(select(User).where(User.legacy_user_id == user_id))
        role = db.scalar(select(Role).where(Role.role_code == role_code))
        if user is None:
            return "missing"
        user_id = user.user_id
        if role is None:
            return "invalid"
        if expires_at and (expires_at.tzinfo is None or expires_at <= now()):
            return "expiry"
        moment = now()
        grant = db.scalar(select(UserRole).where(UserRole.user_id == user_id, UserRole.role_id == role.role_id,
            UserRole.granted_at <= moment, UserRole.revoked_at.is_(None),
            or_(UserRole.expires_at.is_(None), UserRole.expires_at > moment)))
        expands_access = granted and (role_code not in open_roles(user_id, db) or
            (grant and grant.expires_at and (expires_at is None or expires_at > instant(grant.expires_at))))
        if role_code == "admin" and (not granted or expires_at):
            moment = now()
            active_admins = [g.user_id for g in db.scalars(select(UserRole).join(User).where(
                User.account_status == "active", UserRole.role_id == role.role_id))
                if grant_is_active(g, moment)]
            if user_id in active_admins and (user_id == actor.user_id or len(active_admins) <= 1):
                return "last_admin"
        moment = now()
        if granted:
            same_expiry = expires_at == (instant(grant.expires_at) if grant is not None and grant.expires_at else None)
            if grant is not None and not same_expiry:
                grant.revoked_at = moment
                audit(db, actor.user_id, 'role.superseded', 'role_grant', grant.grant_id)
                db.flush()
                grant = None
            if grant is None:
                grant = UserRole(user_id=user_id, role_id=role.role_id, granted_at=moment, expires_at=expires_at)
                db.add(grant)
                db.flush()
        elif grant:
            grant.revoked_at = moment
        if expands_access:
            # A previously stolen token must not inherit newly granted privileges.
            db.execute(delete(AuthSession).where(AuthSession.user_id == user_id))
            audit(db, actor.user_id, "auth.sessions_revoked_on_grant", "account", user_id)
        audit(db, actor.user_id, "role.grant" if granted else "role.revoke",
              "role_grant", grant.grant_id if grant else f"{user_id}:{role_code}")
        return "ok"

