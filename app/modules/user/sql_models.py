import uuid as uuid_pkg
from datetime import datetime

import uuid as uuid
from sqlmodel import SQLModel, Field

from app.modules.user.enum import UserRole, UserStatus


class User(SQLModel, table=True):
    """Пользователь узла"""

    __tablename__ = 'users'

    uuid: uuid_pkg.UUID = Field(primary_key=True, nullable=False, index=True, default_factory=uuid_pkg.uuid4)

    # роль на узле
    role: str = Field(nullable=False, default=UserRole.USER.value)
    # статус пользователя на узле
    status: str = Field(nullable=False, default=UserStatus.UNVERIFIED.value)

    # логин
    login: str = Field(nullable=False, unique=True)
    # электропочта
    email: str = Field(nullable=False, unique=True)
    # хэшированный пароль пользователя
    hashed_password: str = Field(nullable=False)
    # зашифрованная динамическая соль
    cipher_dynamic_salt: str = Field(nullable=False)

    # время создания User
    create_datetime: datetime = Field(nullable=False, default_factory=datetime.utcnow)
