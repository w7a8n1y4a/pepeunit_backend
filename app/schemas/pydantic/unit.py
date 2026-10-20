import uuid as uuid_pkg
from dataclasses import dataclass
from datetime import datetime

from fastapi import Query
from pydantic import BaseModel, root_validator

from app.dto.enum import (
    LogLevel,
    OrderByDate,
    OrderByText,
    UnitFirmwareUpdateStatus,
    UnitIOTypeEnum,
    VisibilityLevel,
)
from app.schemas.pydantic.pagination import BasePaginationRestMixin
from app.schemas.pydantic.shared import UnitIORead


class UnitStateRead(BaseModel):
    ifconfig: list = []
    millis: float | None = None
    mem_free: float | None = None
    mem_alloc: float | None = None
    freq: float | None = None
    statvfs: list = []
    pu_commit_version: str | None = None

    @root_validator(pre=True)
    def check_types(cls, values):
        annotations = cls.__annotations__
        for field, expected_type in annotations.items():
            value = values.get(field, None)
            if isinstance(value, int):
                try:
                    value = float(value)
                    values[field] = value
                except ValueError, TypeError:
                    value = None
                    values[field] = value

            if not isinstance(value, expected_type):
                values[field] = [] if expected_type is list else None
        return values


class UnitRead(BaseModel):
    uuid: uuid_pkg.UUID
    icon_uuid: uuid_pkg.UUID
    visibility_level: VisibilityLevel

    name: str
    create_datetime: datetime

    is_auto_update_unit: bool
    is_compilable_unit: bool
    is_only_tag_update: bool

    target_firmware_platform: str | None = None

    target_branch: str
    target_commit: str | None = None

    unit_state: UnitStateRead | None = None
    current_commit_version: str | None = None

    last_update_datetime: datetime

    creator_uuid: uuid_pkg.UUID
    repository_registry_uuid: uuid_pkg.UUID

    firmware_update_status: UnitFirmwareUpdateStatus | None = None
    firmware_update_error: str | None = None
    last_firmware_update_datetime: datetime | None = None

    # only if requested
    unit_ios: list[UnitIORead] = []


class UnitsResult(BaseModel):
    count: int
    units: list[UnitRead]


class UnitLogRead(BaseModel):
    uuid: uuid_pkg.UUID
    level: LogLevel
    unit_uuid: uuid_pkg.UUID
    text: str
    create_datetime: datetime
    expiration_datetime: datetime


class UnitLogsResult(BaseModel):
    count: int
    unit_logs: list[UnitLogRead]


class TargetVersionRead(BaseModel):
    commit: str
    tag: str | None = None


class UnitCreate(BaseModel):
    repository_registry_uuid: uuid_pkg.UUID

    visibility_level: VisibilityLevel
    name: str

    target_branch: str
    is_compilable_unit: bool = False
    is_auto_update_unit: bool = True
    is_only_tag_update: bool = True

    target_firmware_platform: str | None = None
    target_commit: str | None = None


class UnitUpdate(BaseModel):
    visibility_level: VisibilityLevel | None = None
    name: str | None = None

    target_branch: str | None = None
    is_compilable_unit: bool | None = None
    is_auto_update_unit: bool | None = None
    is_only_tag_update: bool | None = None

    target_firmware_platform: str | None = None
    target_commit: str | None = None


@dataclass
class UnitFilter(BasePaginationRestMixin):
    uuids: list[uuid_pkg.UUID] | None = Query([])

    creator_uuid: uuid_pkg.UUID | None = None
    repository_registry_uuid: uuid_pkg.UUID | None = None

    search_string: str | None = None

    is_auto_update_unit: bool | None = None

    visibility_level: list[str] | None = Query(
        [item.value for item in VisibilityLevel]
    )

    order_by_unit_name: OrderByText | None = OrderByText.asc
    order_by_create_date: OrderByDate | None = OrderByDate.desc
    order_by_last_update: OrderByDate | None = OrderByDate.desc

    # Only with is_include_output_unit_ios = True
    unit_io_input_uuid: uuid_pkg.UUID | None = None
    # Only with is_include_output_unit_ios = True and unit_io_input_uuid == None
    unit_io_type: list[str] | None = Query(
        [item.value for item in UnitIOTypeEnum]
    )
    # Only with is_include_output_unit_ios = True and unit_io_input_uuid == None
    unit_io_uuids: list[uuid_pkg.UUID] | None = Query([])

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
class UnitLogFilter(BasePaginationRestMixin):
    uuid: uuid_pkg.UUID

    level: list[str] | None = Query([item.value for item in LogLevel])

    order_by_create_date: OrderByDate | None = OrderByDate.desc

    def dict(self):
        return self.__dict__
