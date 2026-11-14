"""Persistent login attempt budgets; additive identity-only migration."""
from alembic import op
import sqlalchemy as sa

revision = "auth_002"
down_revision = "auth_001"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("login_throttles",
        sa.Column("key_hash", sa.String(64), primary_key=True),
        sa.Column("attempts", sa.Integer, nullable=False),
        sa.Column("expires_at", sa.String(40), nullable=False))
    op.create_index("ix_login_throttles_expires_at", "login_throttles", ["expires_at"])

def downgrade():
    raise RuntimeError("Destructive identity downgrade is disabled")
