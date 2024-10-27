import uuid as uuid_pkg

import strawberry
from strawberry.types import Info

from app.configs.gql import get_unit_node_service
from app.schemas.gql.inputs.unit_node import UnitNodeEdgeOutputFilterInput, UnitNodeFilterInput
from app.schemas.gql.types.unit import UnitType
from app.schemas.gql.types.unit_node import UnitNodeOutputType, UnitNodeType
from app.schemas.pydantic.unit_node import UnitNodeRead


@strawberry.field()
def get_unit_node(uuid: uuid_pkg.UUID, info: Info) -> UnitNodeType:
    unit_node_service = get_unit_node_service(info)
    return UnitNodeType(**unit_node_service.get(uuid).dict())


@strawberry.field()
def get_unit_nodes(filters: UnitNodeFilterInput, info: Info) -> list[UnitNodeType]:
    unit_node_service = get_unit_node_service(info)
    return [UnitNodeType(**unit_node.dict()) for unit_node in unit_node_service.list(filters)]


@strawberry.field()
def get_output_unit_nodes(filters: UnitNodeEdgeOutputFilterInput, info: Info) -> list[UnitNodeOutputType]:
    unit_node_service = get_unit_node_service(info)
    return [
        UnitNodeOutputType(
            unit=UnitType(**item[0].dict()),
            unit_output_nodes=[UnitNodeType(**UnitNodeRead(**node).dict()) for node in item[1]],
        )
        for item in unit_node_service.get_output_unit_nodes(filters)
    ]
