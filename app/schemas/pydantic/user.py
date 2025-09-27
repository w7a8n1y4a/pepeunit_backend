import uuid as uuid_pkg
from dataclasses import dataclass
from datetime import datetime

from fastapi import Query
from pydantic import BaseModel

from app.dto.enum import OrderByDate, UserRole, UserStatus


class UserRead(BaseModel):
    uuid: uuid_pkg.UUID
    role: UserRole
    status: UserStatus
    login: str
    grafana_org_name: uuid_pkg.UUID
    grafana_org_id: str | None = None
    create_datetime: datetime


class UsersResult(BaseModel):
    count: int
    users: list[UserRead]


class UserCreate(BaseModel):
    login: str
    password: str


class UserUpdate(BaseModel):
    login: str | None = None
    password: str | None = None


class UserAuth(BaseModel):
    credentials: str
    password: str


class AccessToken(BaseModel):
    token: str


@dataclass
class UserFilter:
    uuids: list[uuid_pkg.UUID] | None = Query([])

    search_string: str | None = None

    role: list[str] | None = Query([item.value for item in UserRole])
    status: list[str] | None = Query([item.value for item in UserStatus])

    order_by_create_date: OrderByDate | None = OrderByDate.desc

    offset: int | None = None
    limit: int | None = None

    def dict(self):
        return self.__dict__
