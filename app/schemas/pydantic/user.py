import uuid as uuid_pkg
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from fastapi import Query
from pydantic import BaseModel

from app.dto.enum import OrderByDate, UserRole, UserStatus


class UserRead(BaseModel):
    uuid: uuid_pkg.UUID
    role: UserRole
    status: UserStatus
    login: str
    grafana_org_name: uuid_pkg.UUID
    grafana_org_id: Optional[str] = None
    create_datetime: datetime


class UsersResult(BaseModel):
    count: int
    users: list[UserRead]


class UserCreate(BaseModel):
    login: str
    password: str


class UserUpdate(BaseModel):
    login: Optional[str] = None
    password: Optional[str] = None


class UserAuth(BaseModel):
    credentials: str
    password: str


class AccessToken(BaseModel):
    token: str


@dataclass
class UserFilter:
    uuids: Optional[list[uuid_pkg.UUID]] = Query([])

    search_string: Optional[str] = None

    role: Optional[list[str]] = Query([item.value for item in UserRole])
    status: Optional[list[str]] = Query([item.value for item in UserStatus])

    order_by_create_date: Optional[OrderByDate] = OrderByDate.desc

    offset: Optional[int] = None
    limit: Optional[int] = None

    def dict(self):
        return self.__dict__
