import uuid as uuid_pkg
from datetime import datetime

from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    """Instance user"""

    __tablename__ = "users"

    uuid: uuid_pkg.UUID = Field(
        primary_key=True,
        nullable=False,
        index=True,
        default_factory=uuid_pkg.uuid4,
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
    public_key: str = Field(nullable=False, unique=True, max_length=4096)
    # SHA-256 hex of the raw public key. Challenge lookup uses this.
    hash_public_key: str = Field(nullable=False, unique=True, max_length=64)

    # uuid name in grafana organisation, unique for all users
    grafana_org_name: uuid_pkg.UUID = Field(
        nullable=False, default_factory=uuid_pkg.uuid4
    )
    # id grafana org from grafana
    grafana_org_id: str = Field(nullable=True)

    create_datetime: datetime = Field(nullable=False)
