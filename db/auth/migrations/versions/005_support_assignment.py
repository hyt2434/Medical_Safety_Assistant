"""Explicit support assignment permission; no implicit access to patient data."""
from datetime import datetime, timezone
from alembic import op
import sqlalchemy as sa

revision = 'auth_005'
down_revision = 'auth_004'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    bind.execute(sa.text("INSERT INTO permissions(code,description) VALUES ('operations.assign','Assign technical support tickets') ON CONFLICT(code) DO NOTHING"))
    bind.execute(sa.text("INSERT INTO role_permissions(role_id,permission_code) SELECT role_id,'operations.assign' FROM roles WHERE role_code='admin' ON CONFLICT(role_id,permission_code) DO NOTHING"))
    audit = sa.table('audit_events',sa.column('actor_user_id',sa.Uuid(as_uuid=False)),
        sa.column('action_code',sa.String),sa.column('target_type',sa.String),sa.column('target_id',sa.String),
        sa.column('success',sa.Boolean),sa.column('occurred_at',sa.DateTime(timezone=True)))
    bind.execute(audit.insert().values(actor_user_id=None, action_code='permission.introduced',
        target_type='permission', target_id='operations.assign', success=True, occurred_at=datetime.now(timezone.utc)))


def downgrade():
    raise RuntimeError('Permission and authentication audit history is retained')
