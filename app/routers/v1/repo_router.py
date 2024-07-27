import logging

from fastapi import APIRouter, Depends, status
from fastapi_utilities import repeat_at

from app.configs.db import get_session
from app.configs.gql import get_repo_service
from app.configs.sub_entities import InfoSubEntity
from app.schemas.pydantic.repo import (
    RepoRead,
    RepoCreate,
    RepoUpdate,
    RepoFilter,
    Credentials,
    CommitRead,
    CommitFilter,
    RepoVersionsRead,
)
from app.services.repo_service import RepoService
from app.services.validators import is_valid_uuid

router = APIRouter()


@router.on_event('startup')
@repeat_at(cron='0 * * * *')
def automatic_update_repositories():
    db = next(get_session())

    repo_service = get_repo_service(InfoSubEntity({'db': db, 'jwt_token': None}))
    repo_service.bulk_update_repositories(is_auto_update=True)

    db.close()


@router.post(
    "",
    response_model=RepoRead,
    status_code=status.HTTP_201_CREATED,
)
def create(data: RepoCreate, repo_service: RepoService = Depends()):
    return repo_service.create(data)


@router.get("/{uuid}", response_model=RepoRead)
def get(uuid: str, repo_service: RepoService = Depends()):
    return repo_service.get(is_valid_uuid(uuid))


@router.get("", response_model=list[RepoRead])
def get_repos(filters: RepoFilter = Depends(RepoFilter), repo_service: RepoService = Depends()):
    return repo_service.list(filters)


@router.get("/branch_commits/{uuid}", response_model=list[CommitRead])
def get_branch_commits(uuid: str, filters: CommitFilter = Depends(CommitFilter), repo_service: RepoService = Depends()):
    return repo_service.get_branch_commits(is_valid_uuid(uuid), filters)


@router.get("/versions/{uuid}", response_model=RepoVersionsRead)
def get_versions(uuid: str, repo_service: RepoService = Depends()):
    return repo_service.get_versions(is_valid_uuid(uuid))


@router.patch("/{uuid}", response_model=RepoRead)
def update(uuid: str, data: RepoUpdate, repo_service: RepoService = Depends()):
    return repo_service.update(is_valid_uuid(uuid), data)


@router.patch("/credentials/{uuid}", response_model=RepoRead)
def update_credentials(uuid: str, data: Credentials, repo_service: RepoService = Depends()):
    return repo_service.update_credentials(is_valid_uuid(uuid), data)


@router.patch("/default_branch/{uuid}", response_model=RepoRead)
def update_default_branch(uuid: str, default_branch: str, repo_service: RepoService = Depends()):
    return repo_service.update_default_branch(is_valid_uuid(uuid), default_branch)


@router.patch("/update_local_repo/{uuid}", status_code=status.HTTP_204_NO_CONTENT)
def update_local_repo(uuid: str, repo_service: RepoService = Depends()):
    return repo_service.update_local_repo(is_valid_uuid(uuid))


@router.patch("/update_units_firmware/{uuid}", status_code=status.HTTP_204_NO_CONTENT)
def update_units_firmware(uuid: str, repo_service: RepoService = Depends()):
    return repo_service.update_units_firmware(is_valid_uuid(uuid))


@router.post("/bulk_update", status_code=status.HTTP_204_NO_CONTENT)
def bulk_update(repo_service: RepoService = Depends()):
    return repo_service.bulk_update_repositories()


@router.delete("/{uuid}", status_code=status.HTTP_204_NO_CONTENT)
def delete(uuid: str, repo_service: RepoService = Depends()):
    return repo_service.delete(is_valid_uuid(uuid))
