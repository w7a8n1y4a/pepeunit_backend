import uuid as uuid_pkg

import strawberry

from app.schemas.gql.type_input_mixin import TypeInputMixin
from app.schemas.gql.types.shared import UnitNodeType
from app.schemas.gql.types.unit import UnitType


@strawberry.type()
class UnitNodeEdgeType(TypeInputMixin):
    uuid: uuid_pkg.UUID
    node_output_uuid: uuid_pkg.UUID
    node_input_uuid: uuid_pkg.UUID
    creator_uuid: strawberry.Private[object]


@strawberry.type()
class UnitNodeOutputType(TypeInputMixin):
    unit: UnitType
    unit_output_nodes: list[UnitNodeType]
