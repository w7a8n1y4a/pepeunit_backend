import uuid as uuid_pkg
from datetime import datetime

from sqlmodel import SQLModel, Field


class User(SQLModel, table=True):
    """Пользователь узла"""

    __tablename__ = 'users'

    uuid: uuid_pkg.UUID = Field(primary_key=True, nullable=False, index=True, default_factory=uuid_pkg.uuid4)

    # роль на узле
    role: str = Field(nullable=False)
    # статус пользователя на узле
    status: str = Field(nullable=False)

    # логин
    login: str = Field(nullable=False, unique=True)
    # сhat id в телеграм
    telegram_chat_id: str = Field(nullable=True, unique=True)
    # хэшированный пароль пользователя
    hashed_password: str = Field(nullable=False)
    # зашифрованная динамическая соль
    cipher_dynamic_salt: str = Field(nullable=False)

    # время создания User
    create_datetime: datetime = Field(nullable=False)
