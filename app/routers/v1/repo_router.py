from fastapi import APIRouter, Depends, status
from fastapi_filter import FilterDepends

from app.schemas.pydantic.repo import RepoRead, RepoCreate, RepoUpdate, RepoFilter
from app.services.repo_service import RepoService

router = APIRouter()


@router.post(
    "",
    response_model=RepoRead,
    status_code=status.HTTP_201_CREATED,
)
def create(
    data: RepoCreate,
    repo_service: RepoService = Depends()
):
    return repo_service.create(data)


@router.get("/{uuid}", response_model=RepoRead)
def get(
    uuid: str,
    repo_service: RepoService = Depends()
):
    return repo_service.get(uuid)

@router.patch("/{id}", response_model=RepoRead)
def update(
    uuid: str,
    data: RepoUpdate,
    repo_service: RepoService = Depends()
):
    return repo_service.update(uuid, data)


@router.delete(
    "/{uuid}",
    status_code=status.HTTP_204_NO_CONTENT
)
def delete(
    uuid: str,
    repo_service: RepoService = Depends()
):
    return repo_service.delete(uuid)


@router.get("", response_model=list[RepoRead])
def get_repos(
    filters: RepoFilter = FilterDepends(RepoFilter),
    repo_service: RepoService = Depends()
):
    return repo_service.list(filters)
