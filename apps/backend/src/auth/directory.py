"""Admin operations revalidate the actor inside the write transaction."""
from sqlalchemy import select, delete
from auth.db import initialize, transaction
from auth.models import User, Role, Permission, UserRole, AuditEvent, AuthSession
from auth.rbac import permissions_for, permission_map
from auth.sessions import audit, open_roles, now, instant, timestamp, resolve_session, grant_is_active

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
                "grants": [{"roleCode": code, "grantedAt": g.granted_at, "expiresAt": g.expires_at,
                            "revokedAt": g.revoked_at} for code, g in grants]})
        return result

def list_audit():
    initialize()
    with transaction() as db:
        rows = db.execute(select(AuditEvent, User.full_name).outerjoin(User, User.user_id == AuditEvent.actor_user_id)
                          .order_by(AuditEvent.event_id.desc()).limit(500)).all()
        return [{"id": e.event_id, "actorUserId": e.actor_user_id, "actorName": name or "Hệ thống",
            "actionCode": e.action_code, "targetType": e.target_type, "targetId": e.target_id,
            "success": bool(e.success), "occurredAt": e.occurred_at} for e, name in rows]

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
        user = db.get(User, user_id)
        role = db.scalar(select(Role).where(Role.role_code == role_code))
        if user is None:
            return "missing"
        if role is None:
            return "invalid"
        if expires_at and (expires_at.tzinfo is None or expires_at <= now()):
            return "expiry"
        grant = db.get(UserRole, (user_id, role.role_id))
        expands_access = granted and (role_code not in open_roles(user_id, db) or
            (grant and grant.expires_at and (expires_at is None or expires_at > instant(grant.expires_at))))
        if role_code == "admin" and (not granted or expires_at):
            moment = now()
            active_admins = [g.user_id for g in db.scalars(select(UserRole).join(User).where(
                User.account_status == "active", UserRole.role_id == role.role_id))
                if grant_is_active(g, moment)]
            if user_id in active_admins and (user_id == actor.user_id or len(active_admins) <= 1):
                return "last_admin"
        moment = timestamp()
        if granted:
            if grant is None:
                grant = UserRole(user_id=user_id, role_id=role.role_id, granted_at=moment)
                db.add(grant)
            grant.granted_at, grant.revoked_at = moment, None
            grant.expires_at = expires_at.isoformat() if expires_at else None
        elif grant:
            grant.revoked_at = moment
        if expands_access:
            # A previously stolen token must not inherit newly granted privileges.
            db.execute(delete(AuthSession).where(AuthSession.user_id == user_id))
            audit(db, actor.user_id, "auth.sessions_revoked_on_grant", "account", user_id)
        audit(db, actor.user_id, "role.grant" if granted else "role.revoke",
              "user_role", f"{user_id}:{role_code}")
        return "ok"

