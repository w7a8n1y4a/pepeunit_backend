import logging
import time
import uuid as uuid_pkg
from typing import Optional

from fastapi import APIRouter, Depends, status
from fastapi_utilities import repeat_at

from app.configs.db import get_session
from app.configs.gql import get_repo_service
from app.configs.sub_entities import InfoSubEntity
from app.configs.utils import acquire_file_lock
from app.schemas.pydantic.repo import (
    CommitFilter,
    CommitRead,
    Credentials,
    PlatformRead,
    RepoCreate,
    RepoFilter,
    RepoRead,
    ReposResult,
    RepoUpdate,
    RepoVersionsRead,
)
from app.services.repo_service import RepoService

router = APIRouter()


@router.on_event('startup')
@repeat_at(cron='0 * * * *')
def automatic_update_repositories():
    lock_fd = acquire_file_lock('tmp/update_repos.lock')

    time.sleep(10)

    if lock_fd:
        logging.info('Run update with lock')
        db = next(get_session())
        try:
            repo_service = get_repo_service(InfoSubEntity({'db': db, 'jwt_token': None}))
            repo_service.bulk_update_repositories(is_auto_update=True)
        except Exception as ex:
            logging.error(ex)
        finally:
            db.close()

    else:
        logging.info('Skip update without lock')

    if lock_fd:
        lock_fd.close()


@router.post(
    "",
    response_model=RepoRead,
    status_code=status.HTTP_201_CREATED,
)
def create(data: RepoCreate, repo_service: RepoService = Depends()):
    return repo_service.create(data)


@router.get("/{uuid}", response_model=RepoRead)
def get(uuid: uuid_pkg.UUID, repo_service: RepoService = Depends()):
    return repo_service.get(uuid)


@router.get("", response_model=ReposResult)
def get_repos(filters: RepoFilter = Depends(RepoFilter), repo_service: RepoService = Depends()):
    count, repos = repo_service.list(filters)
    return ReposResult(count=count, repos=repos)


@router.get("/branch_commits/{uuid}", response_model=list[CommitRead])
def get_branch_commits(
    uuid: uuid_pkg.UUID, filters: CommitFilter = Depends(CommitFilter), repo_service: RepoService = Depends()
):
    return repo_service.get_branch_commits(uuid, filters)


@router.get("/available_platforms/{uuid}", response_model=list[PlatformRead])
def get_available_platforms(
    uuid: uuid_pkg.UUID,
    target_commit: Optional[str] = None,
    target_tag: Optional[str] = None,
    repo_service: RepoService = Depends(),
):
    return [
        PlatformRead(name=platform[0], link=platform[1])
        for platform in repo_service.get_available_platforms(uuid, target_commit, target_tag)
    ]


@router.get("/versions/{uuid}", response_model=RepoVersionsRead)
def get_versions(uuid: uuid_pkg.UUID, repo_service: RepoService = Depends()):
    return repo_service.get_versions(uuid)


@router.patch("/{uuid}", response_model=RepoRead)
def update(uuid: uuid_pkg.UUID, data: RepoUpdate, repo_service: RepoService = Depends()):
    return repo_service.update(uuid, data)


@router.patch("/credentials/{uuid}", response_model=RepoRead)
def update_credentials(uuid: uuid_pkg.UUID, data: Credentials, repo_service: RepoService = Depends()):
    return repo_service.update_credentials(uuid, data)


@router.patch("/update_local_repo/{uuid}", status_code=status.HTTP_204_NO_CONTENT)
def update_local_repo(uuid: uuid_pkg.UUID, repo_service: RepoService = Depends()):
    return repo_service.update_local_repo(uuid)


@router.patch("/update_units_firmware/{uuid}", status_code=status.HTTP_204_NO_CONTENT)
def update_units_firmware(uuid: uuid_pkg.UUID, repo_service: RepoService = Depends()):
    return repo_service.update_units_firmware(uuid)


@router.post("/bulk_update", status_code=status.HTTP_204_NO_CONTENT)
def bulk_update(repo_service: RepoService = Depends()):
    return repo_service.bulk_update_repositories()


@router.delete("/{uuid}", status_code=status.HTTP_204_NO_CONTENT)
def delete(uuid: uuid_pkg.UUID, repo_service: RepoService = Depends()):
    return repo_service.delete(uuid)
