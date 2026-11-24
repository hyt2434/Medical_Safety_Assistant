"""Adopt existing identity records without resetting grants or passwords."""
from alembic import op
import sqlalchemy as sa
revision = "auth_001"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    definitions = {
        "users": [sa.Column("user_id", sa.String(80), primary_key=True), sa.Column("email", sa.String(200), nullable=False, unique=True), sa.Column("password_hash", sa.Text, nullable=False), sa.Column("full_name", sa.String(200), nullable=False), sa.Column("account_status", sa.String(20), nullable=False), sa.CheckConstraint("account_status IN ('active','locked')")],
        "roles": [sa.Column("role_id", sa.Integer, primary_key=True), sa.Column("role_code", sa.String(40), nullable=False, unique=True), sa.Column("role_name", sa.String(100), nullable=False)],
        "permissions": [sa.Column("code", sa.String(80), primary_key=True), sa.Column("description", sa.Text, nullable=False)],
        "user_roles": [sa.Column("user_id", sa.String(80), sa.ForeignKey("users.user_id", ondelete="RESTRICT"), primary_key=True), sa.Column("role_id", sa.Integer, sa.ForeignKey("roles.role_id", ondelete="RESTRICT"), primary_key=True), sa.Column("granted_at", sa.String(40), nullable=False), sa.Column("expires_at", sa.String(40)), sa.Column("revoked_at", sa.String(40))],
        "role_permissions": [sa.Column("role_id", sa.Integer, sa.ForeignKey("roles.role_id", ondelete="RESTRICT"), primary_key=True), sa.Column("permission_code", sa.String(80), sa.ForeignKey("permissions.code", ondelete="RESTRICT"), primary_key=True)],
        "auth_sessions": [sa.Column("token_hash", sa.String(64), primary_key=True), sa.Column("user_id", sa.String(80), sa.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False), sa.Column("expires_at", sa.String(40), nullable=False), sa.Column("active_context", sa.String(40))],
        "audit_events": [sa.Column("event_id", sa.Integer, primary_key=True), sa.Column("actor_user_id", sa.String(80)), sa.Column("action_code", sa.String(80), nullable=False), sa.Column("target_type", sa.String(80), nullable=False), sa.Column("target_id", sa.String(200), nullable=False), sa.Column("success", sa.Integer, nullable=False), sa.Column("occurred_at", sa.String(40), nullable=False), sa.CheckConstraint("success IN (0,1)")],
    }
    for name, columns in definitions.items():
        if name not in tables:
            op.create_table(name, *columns)
    if "active_context" not in {c["name"] for c in sa.inspect(bind).get_columns("auth_sessions")}:
        op.add_column("auth_sessions", sa.Column("active_context", sa.String(40)))
    for table, column in [("user_roles", "role_id"), ("auth_sessions", "user_id"), ("auth_sessions", "expires_at"), ("audit_events", "occurred_at")]:
        name = f"ix_{table}_{column}"
        if name not in {i["name"] for i in sa.inspect(bind).get_indexes(table)}:
            op.create_index(name, table, [column])
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email_normalized ON users (lower(email))")

def downgrade():
    raise RuntimeError("Identity history is retained; destructive downgrade is not supported")

