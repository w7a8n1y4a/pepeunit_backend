from fastapi import APIRouter, Depends, status

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

router = APIRouter()


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


@router.delete("/{uuid}", status_code=status.HTTP_204_NO_CONTENT)
def delete(uuid: str, repo_service: RepoService = Depends()):
    return repo_service.delete(uuid)
