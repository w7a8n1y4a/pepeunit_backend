import uuid as uuid_pkg

import strawberry
from strawberry.types import Info

from app.configs.gql import get_unit_node_service_gql
from app.schemas.gql.inputs.unit_node import UnitNodeFilterInput
from app.schemas.gql.types.shared import UnitNodesResultType, UnitNodeType


@strawberry.field()
def get_unit_node(uuid: uuid_pkg.UUID, info: Info) -> UnitNodeType:
    unit_node_service = get_unit_node_service_gql(info)
    return UnitNodeType(**unit_node_service.get(uuid).dict())


@strawberry.field()
def get_unit_nodes(filters: UnitNodeFilterInput, info: Info) -> UnitNodesResultType:
    unit_node_service = get_unit_node_service_gql(info)
    count, unit_nodes = unit_node_service.list(filters)
    return UnitNodesResultType(count=count, unit_nodes=[UnitNodeType(**unit_node.dict()) for unit_node in unit_nodes])
