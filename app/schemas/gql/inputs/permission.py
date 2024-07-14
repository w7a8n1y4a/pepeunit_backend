
import uuid as uuid_pkg
import strawberry

from app.repositories.enum import PermissionEntities
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
