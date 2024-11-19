import uuid as uuid_pkg
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from fastapi import Query
from pydantic import BaseModel

from app.repositories.enum import OrderByDate, OrderByText, UnitNodeTypeEnum, VisibilityLevel
from app.schemas.pydantic.shared import UnitNodeRead


class UnitRead(BaseModel):
    uuid: uuid_pkg.UUID
    visibility_level: VisibilityLevel

    name: str
    create_datetime: datetime

    is_auto_update_from_repo_unit: bool

    repo_branch: Optional[str] = None
    repo_commit: Optional[str] = None

    unit_state_dict: Optional[str] = None
    current_commit_version: Optional[str] = None

    last_update_datetime: datetime

    creator_uuid: uuid_pkg.UUID
    repo_uuid: uuid_pkg.UUID

    # only if requested
    output_unit_nodes: list[UnitNodeRead] = []


class UnitsResult(BaseModel):
    count: int
    units: list[UnitRead]


class UnitCreate(BaseModel):
    repo_uuid: uuid_pkg.UUID

    visibility_level: VisibilityLevel
    name: str

    is_auto_update_from_repo_unit: bool

    repo_branch: Optional[str] = None
    repo_commit: Optional[str] = None


class UnitUpdate(BaseModel):
    visibility_level: Optional[VisibilityLevel] = None
    name: Optional[str] = None

    is_auto_update_from_repo_unit: Optional[bool] = None

    repo_branch: Optional[str] = None
    repo_commit: Optional[str] = None


@dataclass
class UnitFilter:
    uuids: Optional[list[uuid_pkg.UUID]] = Query([])

    creator_uuid: Optional[uuid_pkg.UUID] = None
    repo_uuid: Optional[uuid_pkg.UUID] = None

    search_string: Optional[str] = None

    is_auto_update_from_repo_unit: Optional[bool] = None

    visibility_level: Optional[list[str]] = Query([item.value for item in VisibilityLevel])

    order_by_unit_name: Optional[OrderByText] = OrderByText.asc
    order_by_create_date: Optional[OrderByDate] = OrderByDate.desc
    order_by_last_update: Optional[OrderByDate] = OrderByDate.desc

    offset: Optional[int] = None
    limit: Optional[int] = None

    # only with outputUnitNodes requested
    unit_node_input_uuid: Optional[uuid_pkg.UUID] = None
    # nly with outputUnitNodes requested and unit_node_input_uuid == None
    unit_node_type: Optional[list[str]] = Query([item.value for item in UnitNodeTypeEnum])

    def dict(self):
        return self.__dict__


class UnitMqttTokenAuth(BaseModel):
    token: str
    topic: str
