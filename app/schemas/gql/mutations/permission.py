import strawberry
from strawberry.types import Info

from app.configs.gql import get_permission_service
from app.schemas.gql.inputs.permission import PermissionCreateInput
from app.schemas.gql.types.permission import PermissionType
from app.schemas.gql.types.shared import NoneType


@strawberry.mutation
def create_permission(info: Info, permission: PermissionCreateInput) -> PermissionType:
    permission_service = get_permission_service(info)
    return PermissionType(**permission_service.create(permission).dict())


@strawberry.mutation
def delete_permission(info: Info, uuid: str) -> NoneType:
    permission_service = get_permission_service(info)
    permission_service.delete(uuid)
    return NoneType()
