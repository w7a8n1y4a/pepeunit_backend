import uuid as uuid_pkg
from datetime import datetime
from typing import Optional

import strawberry

from app.repositories.enum import VisibilityLevel
from app.schemas.gql.type_input_mixin import TypeInputMixin


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

    last_update_datetime: datetime

    creator_uuid: uuid_pkg.UUID
    repo_uuid: uuid_pkg.UUID

    cipher_env_dict: strawberry.Private[object]
