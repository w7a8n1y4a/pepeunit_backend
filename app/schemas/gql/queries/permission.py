import strawberry
from strawberry.types import Info

from app.configs.gql import get_permission_service_gql
from app.schemas.gql.inputs.permission import PermissionFilterInput
from app.schemas.gql.types.permission import PermissionsType, PermissionType


@strawberry.field()
def get_resource_agents(filters: PermissionFilterInput, info: Info) -> PermissionsType:
    permission_service = get_permission_service_gql(info)
    count, permissions = permission_service.get_resource_agents(filters)
    return PermissionsType(
        count=count, permissions=[PermissionType(**item.dict()) for item in permissions]
    )
