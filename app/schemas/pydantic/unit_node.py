import uuid as uuid_pkg
from dataclasses import dataclass
from typing import Optional

from fastapi import Query
from pydantic import BaseModel

from app.repositories.enum import OrderByDate, OrderByText, UnitNodeTypeEnum, VisibilityLevel
from app.schemas.pydantic.shared import UnitNodeRead
from app.schemas.pydantic.unit import UnitRead


class UnitNodeOutputRead(BaseModel):
    unit: UnitRead
    unit_output_nodes: list[UnitNodeRead]


class UnitNodeUpdate(BaseModel):
    visibility_level: Optional[VisibilityLevel] = None
    is_rewritable_input: Optional[bool] = None


class UnitNodeSetState(BaseModel):
    state: Optional[str] = None


@dataclass
class UnitNodeFilter:
    unit_uuid: Optional[uuid_pkg.UUID] = None
    search_string: Optional[str] = None

    type: Optional[list[str]] = Query([item.value for item in UnitNodeTypeEnum])
    visibility_level: Optional[list[str]] = Query([item.value for item in VisibilityLevel])

    order_by_create_date: Optional[OrderByDate] = OrderByDate.desc

    offset: Optional[int] = None
    limit: Optional[int] = None

    def dict(self):
        return self.__dict__


@dataclass
class UnitNodeEdgeOutputFilter:
    unit_node_input_uuid: uuid_pkg.UUID
    search_string: Optional[str] = None
    creator_uuid: Optional[uuid_pkg.UUID] = None

    visibility_level: Optional[list[str]] = Query([item.value for item in VisibilityLevel])

    order_by_unit_name: Optional[OrderByText] = OrderByText.asc
    order_by_create_date: Optional[OrderByDate] = OrderByDate.desc

    offset: Optional[int] = None
    limit: Optional[int] = None

    def dict(self):
        return self.__dict__


class UnitNodeEdgeRead(BaseModel):
    uuid: uuid_pkg.UUID
    node_output_uuid: uuid_pkg.UUID
    node_input_uuid: uuid_pkg.UUID


class UnitNodeEdgeCreate(BaseModel):
    node_output_uuid: uuid_pkg.UUID
    node_input_uuid: uuid_pkg.UUID
