import json
import uuid as uuid_pkg

import strawberry
from strawberry.types import Info

from app.configs.gql import get_unit_service
from app.schemas.gql.inputs.unit import UnitFilterInput
from app.schemas.gql.types.unit import UnitsResultType, UnitType
from app.schemas.gql.utils import has_selected_field


@strawberry.field()
def get_unit(uuid: uuid_pkg.UUID, info: Info) -> UnitType:
    unit_service = get_unit_service(info)
    return UnitType(**unit_service.get(uuid).dict())


@strawberry.field()
def get_unit_env(uuid: uuid_pkg.UUID, info: Info) -> str:
    unit_service = get_unit_service(info)
    return json.dumps(unit_service.get_env(uuid))


@strawberry.field()
def get_unit_current_schema(uuid: uuid_pkg.UUID, info: Info) -> str:
    unit_service = get_unit_service(info)
    return json.dumps(unit_service.get_current_schema(uuid))


@strawberry.field()
def get_units(filters: UnitFilterInput, info: Info) -> UnitsResultType:
    unit_service = get_unit_service(info)
    count, units = unit_service.list(filters, has_selected_field(info.selected_fields, 'outputUnitNodes'))
    return UnitsResultType(count=count, units=[unit_service.mapper_unit_to_unit_type(unit) for unit in units])
