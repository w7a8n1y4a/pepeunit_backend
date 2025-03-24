import uuid as uuid_pkg
from typing import Optional

import strawberry

from app.dto.enum import PermissionEntities
from app.schemas.gql.type_input_mixin import TypeInputMixin


@strawberry.input()
class PermissionCreateInput(TypeInputMixin):
    agent_uuid: uuid_pkg.UUID
    agent_type: PermissionEntities

    resource_uuid: uuid_pkg.UUID
    resource_type: PermissionEntities


@strawberry.input()
class ResourceInput(TypeInputMixin):
    resource_uuid: uuid_pkg.UUID
    resource_type: PermissionEntities


@strawberry.input()
class PermissionFilterInput(TypeInputMixin):
    resource_uuid: uuid_pkg.UUID
    resource_type: PermissionEntities

    agent_type: Optional[PermissionEntities] = None

    offset: Optional[int] = None
    limit: Optional[int] = None
