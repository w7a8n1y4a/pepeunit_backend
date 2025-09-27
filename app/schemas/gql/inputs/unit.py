import uuid as uuid_pkg

import strawberry

from app.dto.enum import (
    LogLevel,
    OrderByDate,
    OrderByText,
    UnitNodeTypeEnum,
    VisibilityLevel,
)
from app.schemas.gql.type_input_mixin import TypeInputMixin


@strawberry.input()
class UnitCreateInput(TypeInputMixin):
    repo_uuid: uuid_pkg.UUID

    visibility_level: VisibilityLevel
    name: str

    is_auto_update_from_repo_unit: bool

    target_firmware_platform: str | None = None

    repo_branch: str | None = None
    repo_commit: str | None = None


@strawberry.input()
class UnitUpdateInput(TypeInputMixin):
    visibility_level: VisibilityLevel | None = None
    name: str | None = None

    is_auto_update_from_repo_unit: bool | None = None

    target_firmware_platform: str | None = None

    repo_branch: str | None = None
    repo_commit: str | None = None


@strawberry.input()
class UnitFilterInput(TypeInputMixin):
    uuids: list[uuid_pkg.UUID] | None = ()

    creator_uuid: uuid_pkg.UUID | None = None
    repo_uuid: uuid_pkg.UUID | None = None
    repos_uuids: list[uuid_pkg.UUID] | None = ()

    search_string: str | None = None

    is_auto_update_from_repo_unit: bool | None = None

    visibility_level: list[VisibilityLevel] | None = tuple(VisibilityLevel)

    order_by_unit_name: OrderByText | None = OrderByText.asc
    order_by_create_date: OrderByDate | None = OrderByDate.desc
    order_by_last_update: OrderByDate | None = OrderByDate.desc

    offset: int | None = None
    limit: int | None = None

    # Only with is_include_output_unit_nodes = True
    unit_node_input_uuid: uuid_pkg.UUID | None = None
    # Only with is_include_output_unit_nodes = True and unit_node_input_uuid == None
    unit_node_type: list[UnitNodeTypeEnum] | None = tuple(UnitNodeTypeEnum)
    # Only with is_include_output_unit_nodes = True and unit_node_input_uuid == None
    unit_node_uuids: list[uuid_pkg.UUID] | None = ()


@strawberry.input()
class UnitLogFilterInput(TypeInputMixin):
    uuid: uuid_pkg.UUID

    level: list[LogLevel] | None = tuple(LogLevel)

    order_by_create_date: OrderByDate | None = OrderByDate.desc

    offset: int | None = None
    limit: int | None = None
