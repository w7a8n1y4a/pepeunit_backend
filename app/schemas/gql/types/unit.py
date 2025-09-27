import uuid as uuid_pkg
from datetime import datetime

import strawberry
from strawberry import field

from app.dto.enum import LogLevel, UnitFirmwareUpdateStatus, VisibilityLevel
from app.schemas.gql.type_input_mixin import TypeInputMixin
from app.schemas.gql.types.shared import UnitNodeType


@strawberry.type()
class UnitStateType(TypeInputMixin):
    ifconfig: list[str] = field(default_factory=list)
    millis: float | None = None
    mem_free: float | None = None
    mem_alloc: float | None = None
    freq: float | None = None
    statvfs: list[float] = field(default_factory=list)
    commit_version: str | None = None


@strawberry.type()
class UnitType(TypeInputMixin):
    uuid: uuid_pkg.UUID
    visibility_level: VisibilityLevel

    name: str
    create_datetime: datetime

    is_auto_update_from_repo_unit: bool

    target_firmware_platform: str | None = None

    repo_branch: str | None = None
    repo_commit: str | None = None

    unit_state: UnitStateType | None = None
    current_commit_version: str | None = None

    last_update_datetime: datetime

    creator_uuid: uuid_pkg.UUID
    repo_uuid: uuid_pkg.UUID

    cipher_env_dict: strawberry.Private[object]
    cipher_state_storage: strawberry.Private[object]
    unit_state_dict: strawberry.Private[object]

    firmware_update_status: UnitFirmwareUpdateStatus | None = None
    firmware_update_error: str | None = None
    last_firmware_update_datetime: datetime | None = None

    # only if requested
    unit_nodes: list[UnitNodeType] = field(default_factory=list)


@strawberry.type()
class UnitsResultType(TypeInputMixin):
    count: int
    units: list[UnitType] = field(default_factory=list)


@strawberry.type()
class UnitLogType(TypeInputMixin):
    uuid: uuid_pkg.UUID
    level: LogLevel
    unit_uuid: uuid_pkg.UUID
    text: str
    create_datetime: datetime
    expiration_datetime: datetime


@strawberry.type()
class UnitLogsResultType(TypeInputMixin):
    count: int
    unit_logs: list[UnitLogType]
