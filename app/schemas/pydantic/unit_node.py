import uuid as uuid_pkg
from typing import Optional

from pydantic import BaseModel
from fastapi_filter.contrib.sqlalchemy import Filter

from app.repositories.enum import OrderByDate, VisibilityLevel, UnitNodeType


class UnitNodeRead(BaseModel):
    uuid: uuid_pkg.UUID

    type: UnitNodeType
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


class UnitNodeFilter(Filter):
    search_string: Optional[str] = None

    type: Optional[UnitNodeType] = None
    visibility_level: Optional[VisibilityLevel] = None

    order_by_create_date: Optional[OrderByDate] = OrderByDate.desc

    offset: Optional[int] = None
    limit: Optional[int] = None
