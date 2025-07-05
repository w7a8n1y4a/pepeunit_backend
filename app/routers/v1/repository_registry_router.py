import uuid as uuid_pkg

from fastapi import APIRouter, Depends, status

from app.configs.rest import get_repository_registry_service
from app.schemas.pydantic.repository_registry import RepositoryRegistryCreate, RepositoryRegistryRead
from app.services.repository_registry_service import RepositoryRegistryService

router = APIRouter()


@router.post(
    "",
    response_model=RepositoryRegistryRead,
    status_code=status.HTTP_201_CREATED,
)
def create(
    data: RepositoryRegistryCreate,
    repository_registry_service: RepositoryRegistryService = Depends(get_repository_registry_service),
):
    return repository_registry_service.create(data)


@router.get("/{uuid}", response_model=RepositoryRegistryRead)
def get(
    uuid: uuid_pkg.UUID,
    repository_registry_service: RepositoryRegistryService = Depends(get_repository_registry_service),
):
    return repository_registry_service.get(uuid)
