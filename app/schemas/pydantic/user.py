import uuid as uuid_pkg
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.modules.user.enum import UserStatus, UserRole
from app.modules.user.examples import ex_user_create, ex_user_read, ex_user_auth, ex_access_token


class UserRead(BaseModel):
    """Экземпляр пользователя"""

    uuid: uuid_pkg.UUID
    role: UserRole
    status: UserStatus
    login: str
    email: str
    create_datetime: datetime

    class Config:
        schema_extra = {"example": ex_user_read}


class UserCreate(BaseModel):
    """Создание пользователя"""

    login: str
    email: str
    password: str

    class Config:
        schema_extra = {"example": ex_user_create}


class UserUpdate(BaseModel):
    """Обновление пользователя"""

    login: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None


class UserAuth(BaseModel):
    """Данные для авторизации пользователя"""

    credentials: str
    password: str

    class Config:
        schema_extra = {"example": ex_user_auth}


class AccessToken(BaseModel):
    """Возврат авторизационного токена"""

    access_token: str

    class Config:
        schema_extra = {"example": ex_access_token}
