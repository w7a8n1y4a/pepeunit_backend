import uuid as uuid_pkg

import strawberry
from strawberry.types import Info

from app.configs.gql import get_repo_service
from app.schemas.gql.inputs.repo import RepoCreateInput, RepoUpdateInput, CredentialsInput
from app.schemas.gql.types.repo import RepoType
from app.schemas.gql.types.shared import NoneType


@strawberry.mutation()
def create_repo(info: Info, repo: RepoCreateInput) -> RepoType:
    repo_service = get_repo_service(info)
    return RepoType(**repo_service.create(repo).dict())


@strawberry.mutation()
def update_repo(info: Info, uuid: uuid_pkg.UUID, repo: RepoUpdateInput) -> RepoType:
    repo_service = get_repo_service(info)
    return RepoType(**repo_service.update(uuid, repo).dict())


@strawberry.mutation()
def update_repo_credentials(info: Info, uuid: uuid_pkg.UUID, data: CredentialsInput) -> RepoType:
    repo_service = get_repo_service(info)
    return RepoType(**repo_service.update_credentials(uuid, data).dict())


@strawberry.mutation()
def update_local_repo(info: Info, uuid: uuid_pkg.UUID) -> NoneType:
    repo_service = get_repo_service(info)
    repo_service.update_local_repo(uuid)
    return NoneType()


@strawberry.mutation()
def update_units_firmware(info: Info, uuid: uuid_pkg.UUID) -> NoneType:
    repo_service = get_repo_service(info)
    repo_service.update_units_firmware(uuid)
    return NoneType()


@strawberry.mutation()
def bulk_update(info: Info) -> NoneType:
    repo_service = get_repo_service(info)
    repo_service.bulk_update_repositories()
    return NoneType()


@strawberry.mutation()
def delete_repo(info: Info, uuid: uuid_pkg.UUID) -> NoneType:
    repo_service = get_repo_service(info)
    repo_service.delete(uuid)
    return NoneType()
