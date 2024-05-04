import uuid as uuid_pkg
from dataclasses import dataclass
from typing import Optional

from fastapi import Query
from pydantic import BaseModel
from fastapi_filter.contrib.sqlalchemy import Filter

from app.repositories.enum import OrderByDate, VisibilityLevel, UnitNodeTypeEnum


class UnitNodeRead(BaseModel):
    uuid: uuid_pkg.UUID

    type: UnitNodeTypeEnum
    visibility_level: VisibilityLevel

    is_rewritable_input: bool

    topic_name: str

    state: Optional[str] = None
    unit_uuid: uuid_pkg.UUID


class UnitNodeUpdate(BaseModel):
    visibility_level: VisibilityLevel
    is_rewritable_input: bool


class UnitNodeSetState(BaseModel):
    state: Optional[str] = None


@dataclass
class UnitNodeFilter:
    unit_uuid: Optional[str] = None
    search_string: Optional[str] = None

    type: Optional[list[str]] = Query([item.value for item in UnitNodeTypeEnum])
    visibility_level: Optional[list[str]] = Query([item.value for item in VisibilityLevel])

    order_by_create_date: Optional[OrderByDate] = OrderByDate.desc

    offset: Optional[int] = None
    limit: Optional[int] = None

    def dict(self):
        return self.__dict__
