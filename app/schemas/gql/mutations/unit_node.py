import uuid as uuid_pkg

import strawberry
from strawberry.file_uploads import Upload
from strawberry.types import Info

from app.configs.gql import get_unit_node_service_gql
from app.schemas.gql.inputs.unit_node import UnitNodeEdgeCreateInput, UnitNodeSetStateInput, UnitNodeUpdateInput
from app.schemas.gql.types.shared import NoneType, UnitNodeType
from app.schemas.gql.types.unit_node import UnitNodeEdgeType


@strawberry.mutation()
def update_unit_node(info: Info, uuid: uuid_pkg.UUID, unit_node: UnitNodeUpdateInput) -> UnitNodeType:
    unit_node_service = get_unit_node_service_gql(info)
    return UnitNodeType(**unit_node_service.update(uuid, unit_node).dict())


@strawberry.mutation()
def set_state_unit_node_input(info: Info, uuid: uuid_pkg.UUID, unit_node: UnitNodeSetStateInput) -> UnitNodeType:
    unit_node_service = get_unit_node_service_gql(info)
    return UnitNodeType(**unit_node_service.set_state_input(uuid, unit_node).dict())


@strawberry.mutation()
def create_unit_node_edge(info: Info, unit_node_edge: UnitNodeEdgeCreateInput) -> UnitNodeEdgeType:
    unit_node_service = get_unit_node_service_gql(info)
    return UnitNodeEdgeType(**unit_node_service.create_node_edge(unit_node_edge).dict())


@strawberry.mutation()
def delete_unit_node_edge(info: Info, input_uuid: uuid_pkg.UUID, output_uuid: uuid_pkg.UUID) -> NoneType:
    unit_node_service = get_unit_node_service_gql(info)
    unit_node_service.delete_node_edge(input_uuid, output_uuid)
    return NoneType()


@strawberry.field()
async def set_data_pipe_config(uuid: uuid_pkg.UUID, file: Upload, info: Info) -> NoneType:
    unit_node_service = get_unit_node_service_gql(info)
    await unit_node_service.set_data_pipe_config(uuid, file)
    return NoneType()
