import uuid as uuid_pkg

import strawberry
from strawberry.types import Info

from app.configs.gql import get_permission_service_gql
from app.schemas.gql.inputs.permission import PermissionCreateInput
from app.schemas.gql.types.permission import PermissionType
from app.schemas.gql.types.shared import NoneType


@strawberry.mutation()
def create_permission(
    info: Info, permission: PermissionCreateInput
) -> PermissionType:
    permission_service = get_permission_service_gql(info)
    return PermissionType(**permission_service.create(permission).dict())


@strawberry.mutation()
def delete_permission(
    info: Info, agent_uuid: uuid_pkg.UUID, resource_uuid: uuid_pkg.UUID
) -> NoneType:
    permission_service = get_permission_service_gql(info)
    permission_service.delete(
        agent_uuid=agent_uuid, resource_uuid=resource_uuid
    )
    return NoneType()
