"""add_tbot

Revision ID: 873752e42534
Revises: 5279f6e19c5c
Create Date: 2024-05-11 16:10:32.184342

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = '873752e42534'
down_revision = '5279f6e19c5c'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('users', sa.Column('telegram_chat_id', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.add_column('users', sa.Column('verification_code', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.drop_constraint('users_email_key', 'users', type_='unique')
    op.create_unique_constraint(None, 'users', ['verification_code'])
    op.create_unique_constraint(None, 'users', ['telegram_chat_id'])
    op.drop_column('users', 'email')
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('users', sa.Column('email', sa.VARCHAR(), autoincrement=False, nullable=False))
    op.drop_constraint(None, 'users', type_='unique')
    op.drop_constraint(None, 'users', type_='unique')
    op.create_unique_constraint('users_email_key', 'users', ['email'])
    op.drop_column('users', 'verification_code')
    op.drop_column('users', 'telegram_chat_id')
    # ### end Alembic commands ###
