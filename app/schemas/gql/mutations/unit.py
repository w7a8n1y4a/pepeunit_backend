import uuid as uuid_pkg

import strawberry
from strawberry.types import Info

from app.configs.gql import get_unit_service_gql
from app.dto.enum import BackendTopicCommand
from app.schemas.gql.inputs.unit import UnitCreateInput, UnitUpdateInput
from app.schemas.gql.types.shared import NoneType
from app.schemas.gql.types.unit import UnitType


@strawberry.mutation()
def create_unit(info: Info, unit: UnitCreateInput) -> UnitType:
    unit_service = get_unit_service_gql(info)
    unit = unit_service.create(unit)
    return unit_service.mapper_unit_to_unit_type((unit, []))


@strawberry.mutation()
def update_unit(info: Info, uuid: uuid_pkg.UUID, unit: UnitUpdateInput) -> UnitType:
    unit_service = get_unit_service_gql(info)
    unit = unit_service.update(uuid, unit)
    return unit_service.mapper_unit_to_unit_type((unit, []))


@strawberry.mutation()
def update_unit_env(info: Info, uuid: uuid_pkg.UUID, env_json_str: str) -> NoneType:
    unit_service = get_unit_service_gql(info)
    unit_service.set_env(uuid, env_json_str)
    return NoneType()


@strawberry.mutation()
def set_state_storage(info: Info, uuid: uuid_pkg.UUID, state: str) -> NoneType:
    unit_service = get_unit_service_gql(info)
    unit_service.set_state_storage(uuid, state)
    return NoneType()


@strawberry.mutation()
def send_command_to_input_base_topic(info: Info, uuid: uuid_pkg.UUID, command: BackendTopicCommand) -> NoneType:
    unit_service = get_unit_service_gql(info)
    unit_service.unit_node_service.command_to_input_base_topic(uuid, command)
    return NoneType()


@strawberry.mutation()
def delete_unit(info: Info, uuid: uuid_pkg.UUID) -> NoneType:
    unit_service = get_unit_service_gql(info)
    unit_service.delete(uuid)
    return NoneType()
