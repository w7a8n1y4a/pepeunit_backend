import uuid as uuid_pkg
from typing import Optional

import strawberry
from strawberry.types import Info

from app.configs.gql import get_repository_registry_service_gql
from app.schemas.gql.inputs.repository_registry import (
    CommitFilterInput,
    RepositoryRegistryFilterInput,
)
from app.schemas.gql.types.repo import (
    CommitType,
)
from app.schemas.gql.types.repository_registry import (
    OneRepositoryRegistryCredentialsType,
    RepositoriesRegistryResultType,
    RepositoryRegistryType,
)


@strawberry.field()
def get_repository_registry(uuid: uuid_pkg.UUID, info: Info) -> RepositoryRegistryType:
    repository_registry_service = get_repository_registry_service_gql(info)
    repository = repository_registry_service.get(uuid)
    return RepositoryRegistryType(
        branches=repository_registry_service.mapper_registry_to_registry_read(
            repository
        ).branches,
        **repository.dict(),
    )


@strawberry.field()
def get_branch_commits(
    uuid: uuid_pkg.UUID, filters: CommitFilterInput, info: Info
) -> list[CommitType]:
    repository_registry_service = get_repository_registry_service_gql(info)
    return [
        CommitType(**commit.dict())
        for commit in repository_registry_service.get_branch_commits(uuid, filters)
    ]


@strawberry.field()
def get_credentials(
    uuid: uuid_pkg.UUID, info: Info
) -> Optional[OneRepositoryRegistryCredentialsType]:
    repository_registry_service = get_repository_registry_service_gql(info)
    return repository_registry_service.get_credentials(uuid)


@strawberry.field()
def get_repositories_registry(
    filters: RepositoryRegistryFilterInput, info: Info
) -> RepositoriesRegistryResultType:
    repository_registry_service = get_repository_registry_service_gql(info)
    count, repositories_registry = repository_registry_service.list(filters)
    return RepositoriesRegistryResultType(
        count=count,
        repositories_registry=[
            RepositoryRegistryType(
                branches=repository_registry_service.mapper_registry_to_registry_read(
                    repo
                ).branches,
                **repo.dict(),
            )
            for repo in repositories_registry
        ],
    )
