import uuid as uuid_pkg
from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from fastapi_filter.contrib.sqlalchemy import Filter

from app.modules.user.enum import UserStatus, UserRole
from app.modules.user.examples import ex_user_create, ex_user_read, ex_user_auth, ex_access_token
from app.repositories.enum import OrderByDate


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


class UserFilter(Filter):
    """Фильтр выборки пользователей"""

    search_string: Optional[str] = None

    role: Optional[UserRole] = None
    status: Optional[UserStatus] = None

    order_by_create_date: Optional[OrderByDate] = OrderByDate.desc

    offset: Optional[int] = None
    limit: Optional[int] = None
