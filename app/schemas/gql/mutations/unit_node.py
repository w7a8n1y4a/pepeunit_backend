import strawberry
from strawberry.types import Info

from app.configs.gql import get_unit_node_service
from app.schemas.gql.inputs.unit_node import UnitNodeUpdateInput, UnitNodeSetStateInput, UnitNodeEdgeCreateInput
from app.schemas.gql.types.shared import NoneType
from app.schemas.gql.types.unit_node import UnitNodeType, UnitNodeEdgeType


@strawberry.mutation
def update_unit_node(info: Info, uuid: str, unit_node: UnitNodeUpdateInput) -> UnitNodeType:
    unit_node_service = get_unit_node_service(info)
    return UnitNodeType(**unit_node_service.update(uuid, unit_node).dict())


@strawberry.mutation
def set_state_unit_node_input(info: Info, uuid: str, unit_node: UnitNodeSetStateInput) -> UnitNodeType:
    unit_node_service = get_unit_node_service(info)
    return UnitNodeType(**unit_node_service.set_state_input(uuid, unit_node).dict())


@strawberry.mutation
def create_unit_node_edge(info: Info, unit_node_edge: UnitNodeEdgeCreateInput) -> UnitNodeEdgeType:
    unit_node_service = get_unit_node_service(info)
    return UnitNodeEdgeType(**unit_node_service.create_node_edge(unit_node_edge).dict())


@strawberry.mutation
def delete_unit_node_edge(info: Info, uuid: str) -> NoneType:
    unit_node_service = get_unit_node_service(info)
    unit_node_service.delete_node_edge(uuid)
    return NoneType()

