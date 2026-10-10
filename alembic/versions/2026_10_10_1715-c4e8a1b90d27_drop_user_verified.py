"""drop user verified status

Revision ID: c4e8a1b90d27
Revises: a9bb19bc3e98
Create Date: 2026-10-10 17:15:00.000000

"""

from alembic import op

revision = "c4e8a1b90d27"
down_revision = "a9bb19bc3e98"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE users SET status = 'Active' "
        "WHERE status IN ('Unverified', 'Verified')"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE users SET status = 'Unverified' WHERE status = 'Active'"
    )
