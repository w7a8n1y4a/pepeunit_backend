"""postges_version_change

Revision ID: 5276216fd8d3
Revises: b552dfb75bb7
Create Date: 2025-09-14 01:03:57.018638

"""

from urllib.parse import urlparse

from alembic import op
from app import settings

# revision identifiers, used by Alembic.
revision = "5276216fd8d3"
down_revision = "b552dfb75bb7"
branch_labels = None
depends_on = None

db_name = urlparse(settings.pu_sqlalchemy_database_url).path.lstrip("/")


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(f"REINDEX DATABASE {db_name};")
        op.execute(f"ALTER DATABASE {db_name} REFRESH COLLATION VERSION;")


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(f"REINDEX DATABASE {db_name};")
        op.execute(f"ALTER DATABASE {db_name} REFRESH COLLATION VERSION;")
