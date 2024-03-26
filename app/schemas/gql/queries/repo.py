import strawberry
from strawberry.types import Info

from app.configs.gql import get_repo_service
from app.schemas.gql.inputs.repo import RepoFilterInput
from app.schemas.gql.types.repo import RepoType


@strawberry.field()
def get_repo(
    uuid: str, info: Info
) -> RepoType:
    repo_service = get_repo_service(info)
    return RepoType(**repo_service.get(uuid).dict())


@strawberry.field()
def get_repos(
    filters: RepoFilterInput, info: Info
) -> list[RepoType]:
    repo_service = get_repo_service(info)
    return [RepoType(**repo.dict()) for repo in repo_service.list(filters)]
