import uuid as uuid_pkg
from typing import Optional

import strawberry
from strawberry.types import Info

from app.configs.gql import get_repo_service_gql
from app.schemas.gql.inputs.repo import RepoFilterInput
from app.schemas.gql.types.repo import (
    PlatformType,
    ReposResultType,
    RepoType,
    RepoVersionsType,
    RepoVersionType,
)


@strawberry.field()
def get_repo(uuid: uuid_pkg.UUID, info: Info) -> RepoType:
    repo_service = get_repo_service_gql(info)
    return RepoType(**repo_service.get(uuid).dict())


@strawberry.field()
def get_repos(filters: RepoFilterInput, info: Info) -> ReposResultType:
    repo_service = get_repo_service_gql(info)
    count, repos = repo_service.list(filters)
    return ReposResultType(count=count, repos=[RepoType(**repo.dict()) for repo in repos])


@strawberry.field()
def get_available_platforms(
    uuid: uuid_pkg.UUID, info: Info, target_commit: Optional[str] = None, target_tag: Optional[str] = None
) -> list[PlatformType]:
    repo_service = get_repo_service_gql(info)
    return [
        PlatformType(name=platform[0], link=platform[1])
        for platform in repo_service.get_available_platforms(uuid, target_commit, target_tag)
    ]


@strawberry.field()
def get_versions(uuid: uuid_pkg.UUID, info: Info) -> RepoVersionsType:
    repo_service = get_repo_service_gql(info)
    item_list = RepoVersionsType(**repo_service.get_versions(uuid).dict())
    item_list.versions = [RepoVersionType(**item) for item in item_list.versions]
    return item_list
