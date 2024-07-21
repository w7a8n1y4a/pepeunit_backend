import uuid as uuid_pkg
from typing import Optional

import strawberry

from app.repositories.enum import VisibilityLevel, UnitNodeTypeEnum
from app.schemas.gql.type_input_mixin import TypeInputMixin


@strawberry.type()
class UnitNodeType(TypeInputMixin):
    uuid: uuid_pkg.UUID

    type: UnitNodeTypeEnum
    visibility_level: VisibilityLevel

    is_rewritable_input: bool

    topic_name: str

    state: Optional[str] = None
    unit_uuid: uuid_pkg.UUID


@strawberry.type()
class UnitNodeEdgeType(TypeInputMixin):
    uuid: uuid_pkg.UUID
    node_output_uuid: uuid_pkg.UUID
    node_input_uuid: uuid_pkg.UUID
