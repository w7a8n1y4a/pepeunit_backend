import uuid as uuid_pkg
from typing import Optional

from fastapi import APIRouter, Depends, status

from app.configs.rest import get_repo_service
from app.schemas.pydantic.repo import (
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


@router.post(
    "",
    response_model=RepoRead,
    status_code=status.HTTP_201_CREATED,
)
def create(data: RepoCreate, repo_service: RepoService = Depends(get_repo_service)):
    return repo_service.create(data)


@router.get("/{uuid}", response_model=RepoRead)
def get(uuid: uuid_pkg.UUID, repo_service: RepoService = Depends(get_repo_service)):
    return repo_service.get(uuid)


@router.get("", response_model=ReposResult)
def get_repos(
    filters: RepoFilter = Depends(RepoFilter),
    repo_service: RepoService = Depends(get_repo_service),
):
    count, repos = repo_service.list(filters)
    return ReposResult(count=count, repos=[RepoRead(**repo.dict()) for repo in repos])


@router.get("/available_platforms/{uuid}", response_model=list[PlatformRead])
def get_available_platforms(
    uuid: uuid_pkg.UUID,
    target_commit: Optional[str] = None,
    target_tag: Optional[str] = None,
    repo_service: RepoService = Depends(get_repo_service),
):
    return [
        PlatformRead(name=platform[0], link=platform[1])
        for platform in repo_service.get_available_platforms(
            uuid, target_commit, target_tag
        )
    ]


@router.get("/versions/{uuid}", response_model=RepoVersionsRead)
def get_versions(
    uuid: uuid_pkg.UUID, repo_service: RepoService = Depends(get_repo_service)
):
    return repo_service.get_versions(uuid)


@router.patch("/{uuid}", response_model=RepoRead)
def update(
    uuid: uuid_pkg.UUID,
    data: RepoUpdate,
    repo_service: RepoService = Depends(get_repo_service),
):
    return repo_service.update(uuid, data)


@router.patch("/update_units_firmware/{uuid}", status_code=status.HTTP_204_NO_CONTENT)
def update_units_firmware(
    uuid: uuid_pkg.UUID, repo_service: RepoService = Depends(get_repo_service)
):
    return repo_service.update_units_firmware(uuid)


@router.post("/bulk_update", status_code=status.HTTP_204_NO_CONTENT)
def bulk_update(repo_service: RepoService = Depends(get_repo_service)):
    return repo_service.bulk_update_units_firmware()


@router.delete("/{uuid}", status_code=status.HTTP_204_NO_CONTENT)
def delete(uuid: uuid_pkg.UUID, repo_service: RepoService = Depends(get_repo_service)):
    return repo_service.delete(uuid)
