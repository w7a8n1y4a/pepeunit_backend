import json
import uuid as uuid_pkg

import strawberry
from strawberry.file_uploads import Upload
from strawberry.types import Info

from app.configs.gql import get_unit_service_gql
from app.schemas.gql.inputs.unit import UnitFilterInput, UnitLogFilterInput
from app.schemas.gql.types.repo import TargetVersionType
from app.schemas.gql.types.unit import (
    UnitLogsResultType,
    UnitLogType,
    UnitsResultType,
    UnitType,
)
from app.schemas.gql.utils import has_selected_field


@strawberry.field()
def get_unit(uuid: uuid_pkg.UUID, info: Info) -> UnitType:
    unit_service = get_unit_service_gql(info)
    return unit_service.mapper_unit_to_unit_type((unit_service.get(uuid), []))


@strawberry.field()
def get_unit_env(uuid: uuid_pkg.UUID, info: Info) -> str:
    unit_service = get_unit_service_gql(info)
    return json.dumps(unit_service.get_env(uuid))


@strawberry.field()
def get_target_version(uuid: uuid_pkg.UUID, info: Info) -> TargetVersionType:
    unit_service = get_unit_service_gql(info)
    return TargetVersionType(**unit_service.get_target_version(uuid).dict())


@strawberry.field()
def get_unit_current_schema(uuid: uuid_pkg.UUID, info: Info) -> str:
    unit_service = get_unit_service_gql(info)
    return json.dumps(unit_service.get_current_schema(uuid))


@strawberry.field()
def get_state_storage(uuid: uuid_pkg.UUID, info: Info) -> str:
    unit_service = get_unit_service_gql(info)
    return unit_service.get_state_storage(uuid)


@strawberry.field()
def get_units(filters: UnitFilterInput, info: Info) -> UnitsResultType:
    unit_service = get_unit_service_gql(info)
    count, units = unit_service.list(
        filters, has_selected_field(info.selected_fields, "unitNodes")
    )
    return UnitsResultType(
        count=count,
        units=[unit_service.mapper_unit_to_unit_type(unit) for unit in units],
    )


@strawberry.field()
def get_unit_logs(
    filters: UnitLogFilterInput, info: Info
) -> UnitLogsResultType:
    unit_service = get_unit_service_gql(info)
    count, unit_logs = unit_service.log_list(filters)
    return UnitLogsResultType(
        count=count,
        unit_logs=[UnitLogType(**unit_log.dict()) for unit_log in unit_logs],
    )


@strawberry.field()
async def get_convert_toml_to_md(file: Upload, info: Info) -> str:
    unit_service = get_unit_service_gql(info)
    return await unit_service.convert_toml_file_to_md(file)
