import strawberry
from strawberry.types import Info

from app.configs.gql import get_unit_node_service
from app.schemas.gql.inputs.unit_node import UnitNodeFilterInput
from app.schemas.gql.types.unit_node import UnitNodeType


@strawberry.field()
def get_unit_node(uuid: str, info: Info) -> UnitNodeType:
    unit_node_service = get_unit_node_service(info)
    return UnitNodeType(**unit_node_service.get(uuid).dict())


@strawberry.field()
def get_unit_nodes(filters: UnitNodeFilterInput, info: Info) -> list[UnitNodeType]:
    unit_node_service = get_unit_node_service(info)
    return [UnitNodeType(**unit_node.dict()) for unit_node in unit_node_service.list(filters)]
