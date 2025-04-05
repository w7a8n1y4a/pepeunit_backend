import uuid as uuid_pkg
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from fastapi import Query
from pydantic import BaseModel, root_validator

from app.dto.enum import LogLevel, OrderByDate, OrderByText, UnitFirmwareUpdateStatus, UnitNodeTypeEnum, VisibilityLevel
from app.schemas.pydantic.shared import UnitNodeRead


class UnitStateRead(BaseModel):
    ifconfig: list = []
    millis: Optional[float] = None
    mem_free: Optional[float] = None
    mem_alloc: Optional[float] = None
    freq: Optional[float] = None
    statvfs: list = []
    commit_version: Optional[str] = None

    @root_validator(pre=True)
    def check_types(cls, values):
        annotations = cls.__annotations__
        for field, expected_type in annotations.items():
            value = values.get(field, None)
            if isinstance(value, int):
                try:
                    value = float(value)
                    values[field] = value
                except (ValueError, TypeError):
                    value = None
                    values[field] = value

            if not isinstance(value, expected_type):
                values[field] = [] if expected_type is list else None
        return values


class UnitRead(BaseModel):
    uuid: uuid_pkg.UUID
    visibility_level: VisibilityLevel

    name: str
    create_datetime: datetime

    is_auto_update_from_repo_unit: bool

    target_firmware_platform: Optional[str] = None

    repo_branch: Optional[str] = None
    repo_commit: Optional[str] = None

    unit_state: Optional[UnitStateRead] = None
    current_commit_version: Optional[str] = None

    last_update_datetime: datetime

    creator_uuid: uuid_pkg.UUID
    repo_uuid: uuid_pkg.UUID

    firmware_update_status: Optional[UnitFirmwareUpdateStatus] = None
    firmware_update_error: Optional[str] = None
    last_firmware_update_datetime: Optional[datetime] = None

    # only if requested
    unit_nodes: list[UnitNodeRead] = []


class UnitsResult(BaseModel):
    count: int
    units: list[UnitRead]


class UnitCreate(BaseModel):
    repo_uuid: uuid_pkg.UUID

    visibility_level: VisibilityLevel
    name: str

    is_auto_update_from_repo_unit: bool

    target_firmware_platform: Optional[str] = None

    repo_branch: Optional[str] = None
    repo_commit: Optional[str] = None


class UnitUpdate(BaseModel):
    visibility_level: Optional[VisibilityLevel] = None
    name: Optional[str] = None

    is_auto_update_from_repo_unit: Optional[bool] = None

    target_firmware_platform: Optional[str] = None

    repo_branch: Optional[str] = None
    repo_commit: Optional[str] = None


@dataclass
class UnitFilter:
    uuids: Optional[list[uuid_pkg.UUID]] = Query([])

    creator_uuid: Optional[uuid_pkg.UUID] = None
    repo_uuid: Optional[uuid_pkg.UUID] = None
    repos_uuids: Optional[list[uuid_pkg.UUID]] = Query([])

    search_string: Optional[str] = None

    is_auto_update_from_repo_unit: Optional[bool] = None

    visibility_level: Optional[list[str]] = Query([item.value for item in VisibilityLevel])

    order_by_unit_name: Optional[OrderByText] = OrderByText.asc
    order_by_create_date: Optional[OrderByDate] = OrderByDate.desc
    order_by_last_update: Optional[OrderByDate] = OrderByDate.desc

    offset: Optional[int] = None
    limit: Optional[int] = None

    # Only with is_include_output_unit_nodes = True
    unit_node_input_uuid: Optional[uuid_pkg.UUID] = None
    # Only with is_include_output_unit_nodes = True and unit_node_input_uuid == None
    unit_node_type: Optional[list[str]] = Query([item.value for item in UnitNodeTypeEnum])
    # Only with is_include_output_unit_nodes = True and unit_node_input_uuid == None
    unit_node_uuids: Optional[list[uuid_pkg.UUID]] = Query([])

    def dict(self):
        return self.__dict__


class UnitMqttTokenAuth(BaseModel):
    token: str
    topic: str


class StateStorage(BaseModel):
    state: str


class EnvJsonString(BaseModel):
    env_json_string: str


@dataclass
class UnitLogFilter:
    uuid: uuid_pkg.UUID

    level: Optional[list[str]] = Query([item.value for item in LogLevel])

    order_by_create_date: Optional[OrderByDate] = OrderByDate.desc

    offset: Optional[int] = None
    limit: Optional[int] = None

    def dict(self):
        return self.__dict__
