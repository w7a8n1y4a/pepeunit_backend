import uuid as uuid_pkg
from datetime import datetime
from enum import Enum, UserStatus, UserRole
from typing import Optional

from pydantic import BaseModel
from fastapi_filter.contrib.sqlalchemy import Filter

from app.modules.user.examples import ex_user_create, ex_user_read


class OrderByDate(str, Enum):
    asc = 'asc'
    desc = 'desc'


class UserRead(BaseModel):
    """Экземпляр пользователя"""

    uuid: uuid_pkg.UUID
    role: str
    status: str
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


class UserFilter(Filter):
    """Фильтр выборки пользователей"""

    order_by_create_date: Optional[OrderByDate] = OrderByDate.desc
    search_string: Optional[str] = None
    role: Optional[UserRole] = None
    status: Optional[UserStatus] = None
