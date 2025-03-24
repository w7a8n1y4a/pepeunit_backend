import uuid as uuid_pkg

import strawberry
from strawberry import field

from app.dto.enum import PermissionEntities
from app.schemas.gql.type_input_mixin import TypeInputMixin


@strawberry.type()
class PermissionType(TypeInputMixin):
    uuid: uuid_pkg.UUID

    agent_uuid: uuid_pkg.UUID
    agent_type: PermissionEntities

    resource_uuid: uuid_pkg.UUID
    resource_type: PermissionEntities


@strawberry.type()
class PermissionsType(TypeInputMixin):
    count: int
    permissions: list[PermissionType] = field(default_factory=list)
