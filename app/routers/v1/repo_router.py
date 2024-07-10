import logging

from fastapi import APIRouter, Depends, status
from fastapi_utilities import repeat_at

from app.configs.db import get_session
from app.repositories.permission_repository import PermissionRepository
from app.repositories.repo_repository import RepoRepository
from app.repositories.unit_node_repository import UnitNodeRepository
from app.repositories.unit_repository import UnitRepository
from app.repositories.user_repository import UserRepository
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
from app.services.access_service import AccessService
from app.services.repo_service import RepoService
from app.services.unit_service import UnitService

router = APIRouter()


@router.on_event('startup')
@repeat_at(cron='0 * * * *')
def automatic_update_repositories():
    db = next(get_session())
    repo_repository = RepoRepository(db)
    unit_repository = UnitRepository(db)

    access_service = AccessService(
        permission_repository=PermissionRepository(db),
        unit_repository=unit_repository,
        user_repository=UserRepository(db),
    )

    repo_service = RepoService(
        repo_repository=repo_repository,
        unit_repository=unit_repository,
        unit_service=UnitService(
            repo_repository=repo_repository,
            unit_repository=unit_repository,
            unit_node_repository=UnitNodeRepository(db),
            access_service=access_service,
        ),
        access_service=access_service,
    )

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
    return repo_service.get(uuid)


@router.get("", response_model=list[RepoRead])
def get_repos(filters: RepoFilter = Depends(RepoFilter), repo_service: RepoService = Depends()):
    return repo_service.list(filters)


@router.get("/branch_commits/{uuid}", response_model=list[CommitRead])
def get_branch_commits(uuid: str, filters: CommitFilter = Depends(CommitFilter), repo_service: RepoService = Depends()):
    return repo_service.get_branch_commits(uuid, filters)


@router.get("/versions/{uuid}", response_model=RepoVersionsRead)
def get_versions(uuid: str, repo_service: RepoService = Depends()):
    return repo_service.get_versions(uuid)


@router.patch("/{uuid}", response_model=RepoRead)
def update(uuid: str, data: RepoUpdate, repo_service: RepoService = Depends()):
    return repo_service.update(uuid, data)


@router.patch("/credentials/{uuid}", response_model=RepoRead)
def update_credentials(uuid: str, data: Credentials, repo_service: RepoService = Depends()):
    return repo_service.update_credentials(uuid, data)


@router.patch("/default_branch/{uuid}", response_model=RepoRead)
def update_default_branch(uuid: str, default_branch: str, repo_service: RepoService = Depends()):
    return repo_service.update_default_branch(uuid, default_branch)


@router.patch("/update_local_repo/{uuid}", status_code=status.HTTP_204_NO_CONTENT)
def update_local_repo(uuid: str, repo_service: RepoService = Depends()):
    return repo_service.update_local_repo(uuid)


@router.patch("/update_units_firmware/{uuid}", status_code=status.HTTP_204_NO_CONTENT)
def update_units_firmware(uuid: str, repo_service: RepoService = Depends()):
    return repo_service.update_units_firmware(uuid)


@router.post("/bulk_update", status_code=status.HTTP_204_NO_CONTENT)
def bulk_update(repo_service: RepoService = Depends()):
    return repo_service.bulk_update_repositories()


@router.delete("/{uuid}", status_code=status.HTTP_204_NO_CONTENT)
def delete(uuid: str, repo_service: RepoService = Depends()):
    return repo_service.delete(uuid)
