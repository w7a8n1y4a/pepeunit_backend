"""repo_migration

Revision ID: b4aada6f12c2
Revises: 21a3d2806b9c
Create Date: 2025-06-27 01:27:14.831090

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'b4aada6f12c2'
down_revision = '21a3d2806b9c'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        '_temp_unique_repos',
        sa.Column('repo_url', sa.String(), nullable=False, unique=True),
        sa.Column('platform', sa.String(), nullable=False),
        sa.Column('is_public_repository', sa.Boolean(), nullable=False),
        sa.Column('creator_uuid', postgresql.UUID(), nullable=False),
        sa.Column('create_datetime', sa.DateTime(), nullable=False),
        sa.Column('last_update_datetime', sa.DateTime(), nullable=False)
    )

    op.execute("""
        INSERT INTO _temp_unique_repos (repo_url, platform, is_public_repository, creator_uuid, create_datetime, last_update_datetime)
        SELECT DISTINCT ON (repo_url) 
            repo_url, 
            platform, 
            is_public_repository, 
            creator_uuid, 
            create_datetime, 
            last_update_datetime
        FROM repos
    """)

    op.execute("""
        INSERT INTO repository_registry (
            uuid, 
            platform, 
            repository_url, 
            is_public_repository, 
            local_repository_size, 
            create_datetime, 
            last_update_datetime, 
            creator_uuid
        )
        SELECT 
            gen_random_uuid(), 
            platform, 
            repo_url, 
            is_public_repository, 
            0,  -- начальный размер репозитория
            create_datetime, 
            last_update_datetime, 
            creator_uuid
        FROM _temp_unique_repos
    """)

    op.drop_table('_temp_unique_repos')


def downgrade() -> None:
    op.execute("TRUNCATE TABLE repository_registry")
