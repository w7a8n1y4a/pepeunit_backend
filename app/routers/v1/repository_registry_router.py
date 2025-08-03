import logging
import time
import uuid as uuid_pkg
from typing import Optional

from fastapi import APIRouter, Depends, status
from fastapi_utilities import repeat_at

from app.configs.clickhouse import get_hand_clickhouse_client
from app.configs.db import get_hand_session
from app.configs.rest import get_repo_service, get_repository_registry_service
from app.configs.utils import acquire_file_lock
from app.schemas.pydantic.repository_registry import (
    CommitFilter,
    CommitRead,
    Credentials,
    OneRepositoryRegistryCredentials,
    RepositoriesRegistryResult,
    RepositoryRegistryCreate,
    RepositoryRegistryFilter,
    RepositoryRegistryRead,
)
from app.services.repository_registry_service import RepositoryRegistryService

router = APIRouter()


@router.on_event('startup')
@repeat_at(cron='0 * * * *')
def automatic_update_repositories():
    lock_fd = acquire_file_lock('tmp/update_repos.lock')

    time.sleep(10)

    if lock_fd:
        logging.info('Run update with lock')
        with get_hand_session() as db:
            with get_hand_clickhouse_client() as cc:
                repo_service = get_repo_service(db, cc, None)
                repo_service.bulk_update_units_firmware(is_auto_update=True)

    else:
        logging.info('Skip update without lock')

    if lock_fd:
        lock_fd.close()


@router.on_event('startup')
@repeat_at(cron='30 * * * *')
def automatic_update_registry():
    lock_fd = acquire_file_lock('tmp/update_registry.lock')

    time.sleep(10)

    if lock_fd:
        logging.info('Run update with lock')
        with get_hand_session() as db:
            repository_registry_service = get_repository_registry_service(db, None)
            repository_registry_service.sync_local_repository_storage(True)

    else:
        logging.info('Skip update without lock')

    if lock_fd:
        lock_fd.close()


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


@router.patch("/backend_force_sync_local_repository_storage", status_code=status.HTTP_204_NO_CONTENT)
def backend_force_sync(
    repository_registry_service: RepositoryRegistryService = Depends(get_repository_registry_service),
):
    return repository_registry_service.backend_force_sync_local_repository_storage()


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
