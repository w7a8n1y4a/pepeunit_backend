import strawberry
from strawberry.types import Info

from app.configs.gql import get_repo_service
from app.schemas.gql.inputs.repo import RepoCreateInput, RepoUpdateInput, CredentialsInput
from app.schemas.gql.types.repo import RepoType
from app.schemas.gql.types.shared import NoneType


@strawberry.mutation
def create_repo(info: Info, repo: RepoCreateInput) -> RepoType:
    repo_service = get_repo_service(info)
    return RepoType(**repo_service.create(repo).dict())


@strawberry.mutation
def update_repo(info: Info, uuid: str, repo: RepoUpdateInput) -> RepoType:
    repo_service = get_repo_service(info)
    return RepoType(**repo_service.update(uuid, repo).dict())


@strawberry.mutation
def update_repo_credentials(info: Info, uuid: str, data: CredentialsInput) -> RepoType:
    repo_service = get_repo_service(info)
    return RepoType(**repo_service.update_credentials(uuid, data).dict())


@strawberry.mutation
def update_repo_default_branch(info: Info, uuid: str, default_branch: str) -> RepoType:
    repo_service = get_repo_service(info)
    return RepoType(**repo_service.update_default_branch(uuid, default_branch).dict())


@strawberry.mutation
def update_local_repo(info: Info, uuid: str) -> NoneType:
    repo_service = get_repo_service(info)
    repo_service.update_local_repo(uuid)
    return NoneType()


@strawberry.mutation
def update_units_firmware(info: Info, uuid: str) -> NoneType:
    repo_service = get_repo_service(info)
    repo_service.update_units_firmware(uuid)
    return NoneType()


@strawberry.mutation
def delete_repo(info: Info, uuid: str) -> NoneType:
    repo_service = get_repo_service(info)
    repo_service.delete(uuid)
    return NoneType()
