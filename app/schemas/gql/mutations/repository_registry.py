import uuid as uuid_pkg

import strawberry
from strawberry.types import Info

from app.configs.gql import get_repository_registry_service_gql
from app.schemas.gql.inputs.repository_registry import (
    CredentialsInput,
    RepositoryRegistryCreateInput,
)
from app.schemas.gql.types.repository_registry import RepositoryRegistryType
from app.schemas.gql.types.shared import NoneType


@strawberry.mutation()
def create_repository_registry(
    info: Info, repository_registry: RepositoryRegistryCreateInput
) -> RepositoryRegistryType:
    repository_registry_service = get_repository_registry_service_gql(info)
    repository = repository_registry_service.create(repository_registry)
    return RepositoryRegistryType(
        branches=repository_registry_service.mapper_registry_to_registry_read(
            repository
        ).branches,
        **repository.dict(),
    )


@strawberry.mutation()
def set_credentials(
    info: Info, uuid: uuid_pkg.UUID, data: CredentialsInput
) -> NoneType:
    repository_registry_service = get_repository_registry_service_gql(info)
    repository_registry_service.set_credentials(uuid, data)
    return NoneType()


@strawberry.mutation()
def update_local_repository(info: Info, uuid: uuid_pkg.UUID) -> NoneType:
    repository_registry_service = get_repository_registry_service_gql(info)
    repository_registry_service.update_local_repository(uuid)
    return NoneType()


@strawberry.mutation()
def delete_repository_registry(info: Info, uuid: uuid_pkg.UUID) -> NoneType:
    repository_registry_service = get_repository_registry_service_gql(info)
    repository_registry_service.delete(uuid)
    return NoneType()
