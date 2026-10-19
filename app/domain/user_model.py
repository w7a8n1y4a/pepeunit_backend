import uuid as uuid_pkg
from datetime import datetime

from sqlalchemy import Column, ForeignKey, Index, literal_column
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import Field, SQLModel

from app.domain.icon_model import Icon


class User(SQLModel, table=True):
    """Instance user"""

    __tablename__ = "users"
    __table_args__ = (
        Index(
            "users_public_key_key",
            literal_column("md5(public_key::text)"),
            unique=True,
        ),
    )

    uuid: uuid_pkg.UUID = Field(
        primary_key=True,
        nullable=False,
        index=True,
        default_factory=uuid_pkg.uuid4,
    )

    # Default picture is generated from the public key.
    icon_uuid: uuid_pkg.UUID = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey(
                Icon.__table__.c.uuid,
                name="users_icon_uuid_fkey",
                ondelete="RESTRICT",
            ),
            nullable=False,
            index=True,
        )
    )

    # User role on this Instance
    role: str = Field(nullable=False)
    # User status on this Instance
    status: str = Field(nullable=False)

    # Optional display name. Empty until the user sets it.
    login: str | None = Field(default=None, nullable=True)
    # chat_id in Telegram bot
    telegram_chat_id: str = Field(nullable=True, unique=True)
    # ML-DSA-87 public key, standard base64 of the raw 2592-byte key.
    # The key is larger than a btree entry, so uniqueness is the md5 index.
    public_key: str = Field(nullable=False, max_length=4096)
    # SHA-256 hex of the raw public key. Challenge lookup uses this.
    hash_public_key: str = Field(nullable=False, unique=True, max_length=64)

    # uuid name in grafana organisation, unique for all users
    grafana_org_name: uuid_pkg.UUID = Field(
        nullable=False, default_factory=uuid_pkg.uuid4
    )
    # id grafana org from grafana
    grafana_org_id: str = Field(nullable=True)

    create_datetime: datetime = Field(nullable=False)
