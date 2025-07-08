import uuid as uuid_pkg
from typing import Optional

from fastapi import APIRouter, Depends, status

from app.configs.rest import get_repository_registry_service
from app.schemas.pydantic.repository_registry import (
    CommitFilter,
    CommitRead,
    Credentials,
    OneRepositoryRegistryCredentials,
    PlatformRead,
    RepositoriesRegistryResult,
    RepositoryRegistryCreate,
    RepositoryRegistryFilter,
    RepositoryRegistryRead,
)
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
    return repository_registry_service.mapper_registry_to_registry_read(repository_registry_service.create(data))


@router.get("/{uuid}", response_model=RepositoryRegistryRead)
def get(
    uuid: uuid_pkg.UUID,
    repository_registry_service: RepositoryRegistryService = Depends(get_repository_registry_service),
):
    return repository_registry_service.mapper_registry_to_registry_read(repository_registry_service.get(uuid))


@router.get("/branch_commits/{uuid}", response_model=list[CommitRead])
def get_branch_commits(
    uuid: uuid_pkg.UUID,
    filters: CommitFilter = Depends(CommitFilter),
    repository_registry_service: RepositoryRegistryService = Depends(get_repository_registry_service),
):
    return repository_registry_service.get_branch_commits(uuid, filters)


@router.get("/available_platforms/{uuid}", response_model=list[PlatformRead])
def get_available_platforms(
    uuid: uuid_pkg.UUID,
    target_branch: str,
    target_commit: Optional[str] = None,
    target_tag: Optional[str] = None,
    repository_registry_service: RepositoryRegistryService = Depends(get_repository_registry_service),
):
    return [
        PlatformRead(name=platform[0], link=platform[1])
        for platform in repository_registry_service.get_available_platforms(
            uuid, target_branch, target_commit, target_tag
        )
    ]


@router.patch("/set_credentials/{uuid}", status_code=status.HTTP_204_NO_CONTENT)
def set_credentials(
    uuid: uuid_pkg.UUID,
    data: Credentials,
    repository_registry_service: RepositoryRegistryService = Depends(get_repository_registry_service),
):
    return repository_registry_service.set_credentials(uuid, data)


@router.get("/get_credentials/{uuid}", response_model=Optional[OneRepositoryRegistryCredentials])
def get_credentials(
    uuid: uuid_pkg.UUID,
    repository_registry_service: RepositoryRegistryService = Depends(get_repository_registry_service),
):
    return repository_registry_service.get_credentials(uuid)


@router.patch("/update_local_repository/{uuid}", status_code=status.HTTP_204_NO_CONTENT)
def update_local_repository(
    uuid: uuid_pkg.UUID,
    repository_registry_service: RepositoryRegistryService = Depends(get_repository_registry_service),
):
    return repository_registry_service.update_local_repository(uuid)


@router.get("", response_model=RepositoriesRegistryResult)
def get_repos(
    filters: RepositoryRegistryFilter = Depends(RepositoryRegistryFilter),
    repository_registry_service: RepositoryRegistryService = Depends(get_repository_registry_service),
):
    count, repositories_registry = repository_registry_service.list(filters)
    return RepositoriesRegistryResult(
        count=count,
        repositories_registry=[
            repository_registry_service.mapper_registry_to_registry_read(item) for item in repositories_registry
        ],
    )


@router.delete("/{uuid}", status_code=status.HTTP_204_NO_CONTENT)
def delete(
    uuid: uuid_pkg.UUID,
    repository_registry_service: RepositoryRegistryService = Depends(get_repository_registry_service),
):
    return repository_registry_service.delete(uuid)
