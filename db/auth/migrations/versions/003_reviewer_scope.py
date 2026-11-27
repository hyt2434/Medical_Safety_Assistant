"""Separate data review from clinical case review for existing installations."""
from alembic import op
import sqlalchemy as sa

revision = "auth_003"
down_revision = "auth_002"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(sa.text("DELETE FROM role_permissions WHERE permission_code = 'clinical.case_review' "
                       "AND role_id IN (SELECT role_id FROM roles WHERE role_code = 'medical_reviewer')"))


def downgrade():
    raise RuntimeError("Automatic restoration of clinical access is disabled")
