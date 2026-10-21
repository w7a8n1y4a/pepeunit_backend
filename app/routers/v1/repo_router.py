import uuid as uuid_pkg

from fastapi import APIRouter, Depends, status

from app.configs.rest import get_repo_service
from app.schemas.pydantic.repo import (
    CommitFilter,
    CommitRead,
    Credentials,
    OneRepoCredentials,
    PlatformRead,
    RepoCreate,
    RepoFilter,
    RepoRead,
    ReposResult,
)
from app.services.repo_service import RepoService

router = APIRouter()


@router.post(
    "",
    response_model=RepoRead,
    status_code=status.HTTP_201_CREATED,
)
def create(
    data: RepoCreate,
    repo_service: RepoService = Depends(get_repo_service),
):
    return repo_service.mapper_repo_to_repo_read(repo_service.create(data))


@router.get("/{uuid}", response_model=RepoRead)
def get(
    uuid: uuid_pkg.UUID,
    repo_service: RepoService = Depends(get_repo_service),
):
    return repo_service.mapper_repo_to_repo_read(repo_service.get(uuid))


@router.get("/branch_commits/{uuid}", response_model=list[CommitRead])
def get_branch_commits(
    uuid: uuid_pkg.UUID,
    filters: CommitFilter = Depends(CommitFilter),
    repo_service: RepoService = Depends(get_repo_service),
):
    return repo_service.get_branch_commits(uuid, filters)


@router.get("/available_platforms/{uuid}", response_model=list[PlatformRead])
def get_available_platforms(
    uuid: uuid_pkg.UUID,
    target_commit: str | None = None,
    target_tag: str | None = None,
    branch: str | None = None,
    repo_service: RepoService = Depends(get_repo_service),
):
    return [
        PlatformRead(name=platform[0], link=platform[1])
        for platform in repo_service.get_available_platforms(
            uuid, target_commit, target_tag, branch
        )
    ]


@router.patch(
    "/set_credentials/{uuid}", status_code=status.HTTP_204_NO_CONTENT
)
def set_credentials(
    uuid: uuid_pkg.UUID,
    data: Credentials,
    repo_service: RepoService = Depends(get_repo_service),
):
    return repo_service.set_credentials(uuid, data)


@router.get(
    "/get_credentials/{uuid}",
    response_model=OneRepoCredentials | None,
)
def get_credentials(
    uuid: uuid_pkg.UUID,
    repo_service: RepoService = Depends(get_repo_service),
):
    return repo_service.get_credentials(uuid)


@router.patch(
    "/update_local_repository/{uuid}", status_code=status.HTTP_204_NO_CONTENT
)
def update_local_repository(
    uuid: uuid_pkg.UUID,
    repo_service: RepoService = Depends(get_repo_service),
):
    repo_service.schedule_update(uuid)


@router.patch("/update_all", status_code=status.HTTP_204_NO_CONTENT)
def update_all_repos(
    repo_service: RepoService = Depends(get_repo_service),
):
    repo_service.schedule_update_all()


@router.patch("/backend_sync_repo", status_code=status.HTTP_204_NO_CONTENT)
def backend_force_sync(
    repo_service: RepoService = Depends(get_repo_service),
):
    return repo_service.backend_force_sync_local_repository_storage()


@router.get("", response_model=ReposResult)
def get_repos(
    filters: RepoFilter = Depends(RepoFilter),
    repo_service: RepoService = Depends(get_repo_service),
):
    count, repos = repo_service.list(filters)
    return ReposResult(
        count=count,
        repos=[repo_service.mapper_repo_to_repo_read(item) for item in repos],
    )


@router.delete("/{uuid}", status_code=status.HTTP_204_NO_CONTENT)
def delete(
    uuid: uuid_pkg.UUID,
    repo_service: RepoService = Depends(get_repo_service),
):
    return repo_service.delete(uuid)
