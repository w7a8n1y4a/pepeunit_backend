import uuid as uuid_pkg
from datetime import datetime

from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    """Пользователь узла"""

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

    # Unique User login on this Instance
    login: str = Field(nullable=False, unique=True)
    # chat_id in Telegram bot
    telegram_chat_id: str = Field(nullable=True, unique=True)
    hashed_password: str = Field(nullable=False)
    # cipher dynamic salt for hashed password
    cipher_dynamic_salt: str = Field(nullable=False)

    # uuid name in grafana organisation, unique for all users
    grafana_org_name: uuid_pkg.UUID = Field(
        nullable=False, default_factory=uuid_pkg.uuid4
    )
    # id grafana org from grafana
    grafana_org_id: str = Field(nullable=True)

    create_datetime: datetime = Field(nullable=False)
