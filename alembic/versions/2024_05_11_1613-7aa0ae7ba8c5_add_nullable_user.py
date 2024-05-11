"""add_nullable_user

Revision ID: 7aa0ae7ba8c5
Revises: 873752e42534
Create Date: 2024-05-11 16:13:35.796574

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = '7aa0ae7ba8c5'
down_revision = '873752e42534'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('users', 'verification_code',
               existing_type=sa.VARCHAR(),
               nullable=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('users', 'verification_code',
               existing_type=sa.VARCHAR(),
               nullable=True)
    # ### end Alembic commands ###
