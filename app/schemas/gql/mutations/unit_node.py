import strawberry
from strawberry.types import Info

from app.configs.gql import get_unit_node_service
from app.schemas.gql.inputs.unit_node import UnitNodeUpdateInput, UnitNodeSetStateInput
from app.schemas.gql.types.unit_node import UnitNodeType


@strawberry.mutation
def update_unit_node(info: Info, uuid: str, unit_node: UnitNodeUpdateInput) -> UnitNodeType:
    unit_node_service = get_unit_node_service(info)
    return UnitNodeType(**unit_node_service.update(uuid, unit_node).dict())


@strawberry.mutation
def set_state_unit_node_input(info: Info, uuid: str, unit_node: UnitNodeSetStateInput) -> UnitNodeType:
    unit_node_service = get_unit_node_service(info)
    return UnitNodeType(**unit_node_service.set_state_input(uuid, unit_node).dict())
