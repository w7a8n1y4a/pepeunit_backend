import uuid as uuid_pkg

from fastapi import APIRouter, Depends, status

from app.configs.rest import get_permission_service
from app.schemas.pydantic.permission import (
    PermissionCreate,
    PermissionFilter,
    PermissionRead,
    PermissionsRead,
)
from app.services.permission_service import PermissionService

router = APIRouter()


@router.post(
    "",
    response_model=PermissionRead,
    status_code=status.HTTP_201_CREATED,
)
def create(
    data: PermissionCreate,
    permission_service: PermissionService = Depends(get_permission_service),
):
    return PermissionRead(**permission_service.create(data).dict())


@router.get("/get_resource_agents", response_model=PermissionsRead)
def get_resource_agents(
    filters: PermissionFilter = Depends(PermissionFilter),
    permission_service: PermissionService = Depends(get_permission_service),
):
    count, permissions = permission_service.get_resource_agents(filters)
    return PermissionsRead(
        count=count,
        permissions=[PermissionRead(**item.dict()) for item in permissions],
    )


@router.delete("/{uuid}", status_code=status.HTTP_204_NO_CONTENT)
def delete(
    agent_uuid: uuid_pkg.UUID,
    resource_uuid: uuid_pkg.UUID,
    permission_service: PermissionService = Depends(get_permission_service),
):
    return permission_service.delete(
        agent_uuid=agent_uuid, resource_uuid=resource_uuid
    )
