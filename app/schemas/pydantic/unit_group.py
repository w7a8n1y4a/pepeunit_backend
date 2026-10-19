import uuid as uuid_pkg
from dataclasses import dataclass
from datetime import datetime

from fastapi import Query
from pydantic import BaseModel

from app.dto.enum import OrderByDate, OrderByText
from app.schemas.pydantic.pagination import BasePaginationRestMixin


class UnitGroupRead(BaseModel):
    uuid: uuid_pkg.UUID
    icon_uuid: uuid_pkg.UUID
    name: str
    create_datetime: datetime
    creator_uuid: uuid_pkg.UUID


class UnitGroupsResult(BaseModel):
    count: int
    unit_groups: list[UnitGroupRead]


class UnitGroupCreate(BaseModel):
    name: str


class UnitGroupUpdate(BaseModel):
    name: str | None = None


@dataclass
class UnitGroupFilter(BasePaginationRestMixin):
    uuids: list[uuid_pkg.UUID] | None = Query([])

    search_string: str | None = None

    # Groups of the current user that contain this unit.
    unit_uuid: uuid_pkg.UUID | None = None

    order_by_group_name: OrderByText | None = OrderByText.asc
    order_by_create_date: OrderByDate | None = OrderByDate.desc

    def dict(self):
        return self.__dict__


@dataclass
class UnitGroupMemberFilter(BasePaginationRestMixin):
    search_string: str | None = None

    order_by_unit_name: OrderByText | None = OrderByText.asc

    def dict(self):
        return self.__dict__
