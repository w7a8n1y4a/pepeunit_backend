import uuid as uuid_pkg
from datetime import datetime
from typing import Optional

import strawberry
from strawberry import field

from app.dto.enum import UnitNodeTypeEnum, VisibilityLevel
from app.schemas.gql.type_input_mixin import TypeInputMixin


@strawberry.type()
class NoneType(TypeInputMixin):
    is_none: bool = True


@strawberry.type()
class UnitNodeType(TypeInputMixin):
    uuid: uuid_pkg.UUID

    type: UnitNodeTypeEnum
    visibility_level: VisibilityLevel

    is_rewritable_input: bool

    topic_name: str
    last_update_datetime: datetime

    create_datetime: datetime
    state: Optional[str] = None

    unit_uuid: uuid_pkg.UUID
    creator_uuid: uuid_pkg.UUID


@strawberry.type()
class UnitNodesResultType(TypeInputMixin):
    count: int
    unit_nodes: list[UnitNodeType] = field(default_factory=list)
