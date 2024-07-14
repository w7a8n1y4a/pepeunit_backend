import strawberry
from strawberry.types import Info

from app.configs.gql import get_permission_service
from app.schemas.gql.inputs.permission import ResourceInput
from app.schemas.gql.types.permission import PermissionType


@strawberry.field()
def get_resource_agents(data: ResourceInput, info: Info) -> list[PermissionType]:
    permission_service = get_permission_service(info)
    return [PermissionType(**item.dict()) for item in permission_service.get_resource_agents(data)]
