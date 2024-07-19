import strawberry
from strawberry.types import Info

from app.configs.gql import get_unit_service
from app.schemas.gql.inputs.unit import UnitCreateInput, UnitUpdateInput
from app.schemas.gql.types.shared import NoneType
from app.schemas.gql.types.unit import UnitType


@strawberry.mutation
def create_unit(info: Info, unit: UnitCreateInput) -> UnitType:
    unit_service = get_unit_service(info)
    unit = unit_service.create(unit).dict()
    return UnitType(**unit)


@strawberry.mutation
def update_unit(info: Info, uuid: str, unit: UnitUpdateInput) -> UnitType:
    unit_service = get_unit_service(info)
    unit = unit_service.update(uuid, unit).dict()
    return UnitType(**unit)


@strawberry.mutation
def update_unit_env(info: Info, uuid: str, env_json_str: str) -> NoneType:
    unit_service = get_unit_service(info)
    unit_service.set_env(uuid, env_json_str)
    return NoneType()


@strawberry.mutation
def update_unit_schema(info: Info, uuid: str) -> NoneType:
    unit_service = get_unit_service(info)
    unit_service.update_schema(uuid)
    return NoneType()


@strawberry.mutation
def delete_unit(info: Info, uuid: str) -> NoneType:
    unit_service = get_unit_service(info)
    unit_service.delete(uuid)
    return NoneType()
