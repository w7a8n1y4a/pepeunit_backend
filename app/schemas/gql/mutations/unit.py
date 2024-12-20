import uuid as uuid_pkg

import strawberry
from strawberry.types import Info

from app.configs.gql import get_unit_service
from app.repositories.enum import BackendTopicCommand
from app.schemas.gql.inputs.unit import UnitCreateInput, UnitUpdateInput
from app.schemas.gql.types.shared import NoneType
from app.schemas.gql.types.unit import UnitType


@strawberry.mutation()
def create_unit(info: Info, unit: UnitCreateInput) -> UnitType:
    unit_service = get_unit_service(info)
    unit = unit_service.create(unit).dict()
    return UnitType(**unit)


@strawberry.mutation()
def update_unit(info: Info, uuid: uuid_pkg.UUID, unit: UnitUpdateInput) -> UnitType:
    unit_service = get_unit_service(info)
    unit = unit_service.update(uuid, unit).dict()
    return UnitType(**unit)


@strawberry.mutation()
def update_unit_env(info: Info, uuid: uuid_pkg.UUID, env_json_str: str) -> NoneType:
    unit_service = get_unit_service(info)
    unit_service.set_env(uuid, env_json_str)
    return NoneType()


@strawberry.mutation()
def send_command_to_input_base_topic(info: Info, uuid: uuid_pkg.UUID, command: BackendTopicCommand) -> NoneType:
    unit_service = get_unit_service(info)
    unit_service.command_to_input_base_topic(uuid, command)
    return NoneType()


@strawberry.mutation()
def delete_unit(info: Info, uuid: uuid_pkg.UUID) -> NoneType:
    unit_service = get_unit_service(info)
    unit_service.delete(uuid)
    return NoneType()
