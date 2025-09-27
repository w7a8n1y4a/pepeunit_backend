"""aes_cbc_to_gcm

Revision ID: c8284720446d
Revises: 199c13471f04
Create Date: 2025-02-11 08:04:42.552798

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.utils.utils import aes_decode, aes_gcm_encode, aes_gcm_decode, aes_encode

# revision identifiers, used by Alembic.
revision = "c8284720446d"
down_revision = "199c13471f04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    session = Session(bind=bind)

    users = session.execute(
        sa.text("SELECT uuid, cipher_dynamic_salt FROM users")
    ).fetchall()

    for uuid, cipher_dynamic_salt in users:
        if cipher_dynamic_salt:
            new_cipher = aes_gcm_encode(aes_decode(cipher_dynamic_salt))
            session.execute(
                sa.text(
                    f"UPDATE users SET cipher_dynamic_salt = '{new_cipher}' WHERE uuid = '{uuid}'"
                )
            )

    repos = session.execute(
        sa.text("SELECT uuid, cipher_credentials_private_repository FROM repos")
    ).fetchall()

    for uuid, cipher_credentials_private_repository in repos:
        if cipher_credentials_private_repository:
            new_cipher = aes_gcm_encode(
                aes_decode(cipher_credentials_private_repository)
            )
            session.execute(
                sa.text(
                    f"UPDATE repos SET cipher_credentials_private_repository = '{new_cipher}' WHERE uuid = '{uuid}'"
                )
            )

    units = session.execute(
        sa.text("SELECT uuid, cipher_env_dict FROM units")
    ).fetchall()

    for uuid, cipher_env_dict in units:
        if cipher_env_dict:
            new_cipher = aes_gcm_encode(aes_decode(cipher_env_dict))
            session.execute(
                sa.text(
                    f"UPDATE units SET cipher_env_dict = '{new_cipher}' WHERE uuid = '{uuid}'"
                )
            )

    units = session.execute(
        sa.text("SELECT uuid, cipher_state_storage FROM units")
    ).fetchall()

    for uuid, cipher_state_storage in units:
        if cipher_state_storage:
            new_cipher = aes_gcm_encode(aes_decode(cipher_state_storage))
            session.execute(
                sa.text(
                    f"UPDATE units SET cipher_state_storage = '{new_cipher}' WHERE uuid = '{uuid}'"
                )
            )


def downgrade() -> None:
    bind = op.get_bind()
    session = Session(bind=bind)

    users = session.execute(
        sa.text("SELECT uuid, cipher_dynamic_salt FROM users")
    ).fetchall()

    for uuid, cipher_dynamic_salt in users:
        if cipher_dynamic_salt:
            new_cipher = aes_encode(aes_gcm_decode(cipher_dynamic_salt))
            session.execute(
                sa.text(
                    f"UPDATE users SET cipher_dynamic_salt = '{new_cipher}' WHERE uuid = '{uuid}'"
                )
            )

    repos = session.execute(
        sa.text("SELECT uuid, cipher_credentials_private_repository FROM repos")
    ).fetchall()

    for uuid, cipher_credentials_private_repository in repos:
        if cipher_credentials_private_repository:
            new_cipher = aes_encode(
                aes_gcm_decode(cipher_credentials_private_repository)
            )
            session.execute(
                sa.text(
                    f"UPDATE repos SET cipher_credentials_private_repository = '{new_cipher}' WHERE uuid = '{uuid}'"
                )
            )

    units = session.execute(
        sa.text("SELECT uuid, cipher_env_dict FROM units")
    ).fetchall()

    for uuid, cipher_env_dict in units:
        if cipher_env_dict:
            new_cipher = aes_encode(aes_gcm_decode(cipher_env_dict))
            session.execute(
                sa.text(
                    f"UPDATE units SET cipher_env_dict = '{new_cipher}' WHERE uuid = '{uuid}'"
                )
            )

    units = session.execute(
        sa.text("SELECT uuid, cipher_state_storage FROM units")
    ).fetchall()

    for uuid, cipher_state_storage in units:
        if cipher_state_storage:
            new_cipher = aes_encode(aes_gcm_decode(cipher_state_storage))
            session.execute(
                sa.text(
                    f"UPDATE units SET cipher_state_storage = '{new_cipher}' WHERE uuid = '{uuid}'"
                )
            )
