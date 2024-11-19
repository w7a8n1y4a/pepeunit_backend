import uuid as uuid_pkg
from datetime import datetime
from typing import Optional

import strawberry
from strawberry import field

from app.repositories.enum import VisibilityLevel
from app.schemas.gql.type_input_mixin import TypeInputMixin
from app.schemas.gql.types.shared import UnitNodeType


@strawberry.type()
class UnitType(TypeInputMixin):
    uuid: uuid_pkg.UUID
    visibility_level: VisibilityLevel

    name: str
    create_datetime: datetime

    is_auto_update_from_repo_unit: bool

    repo_branch: Optional[str] = None
    repo_commit: Optional[str] = None

    unit_state_dict: Optional[str] = None
    current_commit_version: Optional[str] = None

    last_update_datetime: datetime

    creator_uuid: uuid_pkg.UUID
    repo_uuid: uuid_pkg.UUID

    cipher_env_dict: strawberry.Private[object]

    # only if requested
    unit_nodes: list[UnitNodeType] = field(default_factory=list)


@strawberry.type()
class UnitsResultType(TypeInputMixin):
    count: int
    units: list[UnitType] = field(default_factory=list)
