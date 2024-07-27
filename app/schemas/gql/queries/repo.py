import uuid as uuid_pkg

import strawberry
from strawberry.types import Info

from app.configs.gql import get_repo_service
from app.schemas.gql.inputs.repo import RepoFilterInput, CommitFilterInput
from app.schemas.gql.types.repo import RepoType, CommitType, RepoVersionsType, RepoVersionType


@strawberry.field()
def get_repo(uuid: uuid_pkg.UUID, info: Info) -> RepoType:
    repo_service = get_repo_service(info)
    return RepoType(**repo_service.get(uuid).dict())


@strawberry.field()
def get_repos(filters: RepoFilterInput, info: Info) -> list[RepoType]:
    repo_service = get_repo_service(info)
    return [RepoType(**repo.dict()) for repo in repo_service.list(filters)]


@strawberry.field()
def get_branch_commits(uuid: uuid_pkg.UUID, filters: CommitFilterInput, info: Info) -> list[CommitType]:
    repo_service = get_repo_service(info)
    return [CommitType(**commit.dict()) for commit in repo_service.get_branch_commits(uuid, filters)]


@strawberry.field()
def get_versions(uuid: uuid_pkg.UUID, info: Info) -> RepoVersionsType:
    repo_service = get_repo_service(info)
    item_list = RepoVersionsType(**repo_service.get_versions(uuid).dict())
    item_list.versions = [RepoVersionType(**item) for item in item_list.versions]
    return item_list
