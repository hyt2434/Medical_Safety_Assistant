"""Identity-owned ORM, independent of Core V4."""
from datetime import datetime
from uuid import uuid4
from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, Text, Index, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from shared.auth.types import AccountUUID, AwareTime

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    user_id: Mapped[str] = mapped_column(AccountUUID(), primary_key=True)
    legacy_user_id: Mapped[str | None] = mapped_column(String(80), unique=True)
    email: Mapped[str] = mapped_column(String(200), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    full_name: Mapped[str] = mapped_column(String(200))
    account_status: Mapped[str] = mapped_column(String(20), default="active")
    __table_args__ = (CheckConstraint("account_status IN ('active','locked')"),
                      Index('uq_users_email_normalized', func.lower(email), unique=True))

class Role(Base):
    __tablename__ = "roles"
    role_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    role_code: Mapped[str] = mapped_column(String(40), unique=True)
    role_name: Mapped[str] = mapped_column(String(100))

class Permission(Base):
    __tablename__ = "permissions"
    code: Mapped[str] = mapped_column(String(80), primary_key=True)
    description: Mapped[str] = mapped_column(Text)

class RolePermission(Base):
    __tablename__ = "role_permissions"
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.role_id", ondelete="RESTRICT"), primary_key=True)
    permission_code: Mapped[str] = mapped_column(ForeignKey("permissions.code", ondelete="RESTRICT"), primary_key=True)

class UserRole(Base):
    __tablename__ = "user_roles"
    grant_id: Mapped[str] = mapped_column(AccountUUID(), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id", ondelete="RESTRICT"), index=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.role_id", ondelete="RESTRICT"), index=True)
    granted_at: Mapped[datetime] = mapped_column(AwareTime())
    expires_at: Mapped[datetime | None] = mapped_column(AwareTime())
    revoked_at: Mapped[datetime | None] = mapped_column(AwareTime())
    __table_args__ = (CheckConstraint('expires_at IS NULL OR expires_at > granted_at'),
                      CheckConstraint('revoked_at IS NULL OR revoked_at >= granted_at'),)

class AuthSession(Base):
    __tablename__ = "auth_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(AwareTime(), index=True)
    active_context: Mapped[str | None] = mapped_column(String(40))

class AuditEvent(Base):
    __tablename__ = "audit_events"
    event_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_user_id: Mapped[str | None] = mapped_column(AccountUUID())
    action_code: Mapped[str] = mapped_column(String(80))
    target_type: Mapped[str] = mapped_column(String(80))
    target_id: Mapped[str] = mapped_column(String(200))
    success: Mapped[bool] = mapped_column(Boolean(create_constraint=True, name='audit_success_boolean'))
    occurred_at: Mapped[datetime] = mapped_column(AwareTime(), index=True)

class LoginThrottle(Base):
    __tablename__ = "login_throttles"
    key_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    attempts: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[datetime] = mapped_column(AwareTime(), index=True)
    __table_args__ = (CheckConstraint('attempts >= 0'),)
