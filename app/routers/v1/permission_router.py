from fastapi import APIRouter, Depends, status

from app.schemas.pydantic.permission import PermissionRead, Resource, PermissionCreate
from app.services.permission_service import PermissionService

router = APIRouter()


@router.post(
    "",
    response_model=PermissionRead,
    status_code=status.HTTP_201_CREATED,
)
def create(data: PermissionCreate, permission_service: PermissionService = Depends()):
    return PermissionRead(**permission_service.create(data).dict())


@router.get("/get_resource_agents", response_model=list[PermissionRead])
def get_resource_agents(resource: Resource = Depends(), permission_service: PermissionService = Depends()):

    items = permission_service.get_resource_agents(resource)
    return [PermissionRead(**item.dict()) for item in items]


@router.delete("/{uuid}", status_code=status.HTTP_204_NO_CONTENT)
def delete(uuid: str, permission_service: PermissionService = Depends()):
    return permission_service.delete(uuid)
