import strawberry
from strawberry.types import Info

from app.configs.gql import get_repo_service
from app.schemas.gql.inputs.repo import RepoCreateInput, RepoUpdateInput
from app.schemas.gql.types.repo import RepoType
from app.schemas.gql.types.shared import NoneType


@strawberry.mutation
def create_repo(
    info: Info, repo: RepoCreateInput
) -> RepoType:
    repo_service = get_repo_service(info)
    return RepoType(**repo_service.create(repo).dict())


@strawberry.mutation
def update_repo(
    info: Info, uuid: str, repo: RepoUpdateInput
) -> RepoType:
    repo_service = get_repo_service(info)
    return RepoType(**repo_service.update(uuid, repo).dict())


@strawberry.mutation
def delete_repo(
    info: Info, uuid: str
) -> NoneType:
    repo_service = get_repo_service(info)
    repo_service.delete(uuid)
    return NoneType()
