import uuid as uuid_pkg
from datetime import datetime
from typing import Optional

import strawberry

from app.repositories.enum import UnitNodeTypeEnum, VisibilityLevel
from app.schemas.gql.type_input_mixin import TypeInputMixin
from app.schemas.gql.types.unit import UnitType


@strawberry.type()
class UnitNodeType(TypeInputMixin):
    uuid: uuid_pkg.UUID

    type: UnitNodeTypeEnum
    visibility_level: VisibilityLevel

    is_rewritable_input: bool

    topic_name: str

    create_datetime: datetime
    state: Optional[str] = None

    unit_uuid: uuid_pkg.UUID
    creator_uuid: uuid_pkg.UUID


@strawberry.type()
class UnitNodeEdgeType(TypeInputMixin):
    uuid: uuid_pkg.UUID
    node_output_uuid: uuid_pkg.UUID
    node_input_uuid: uuid_pkg.UUID


@strawberry.type()
class UnitNodeOutputType(TypeInputMixin):
    unit: UnitType
    unit_output_nodes: list[UnitNodeType]
