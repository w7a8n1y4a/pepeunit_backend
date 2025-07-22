import uuid as uuid_pkg
from datetime import datetime
from typing import Optional

import strawberry
from strawberry import field

from app.dto.enum import CredentialStatus, GitPlatform, RepositoryRegistryStatus
from app.schemas.gql.type_input_mixin import TypeInputMixin


@strawberry.type()
class RepositoryRegistryType(TypeInputMixin):
    uuid: uuid_pkg.UUID

    platform: GitPlatform
    repository_url: str

    is_public_repository: bool
    releases_data: Optional[str] = None

    local_repository_size: int

    sync_status: Optional[RepositoryRegistryStatus] = None
    sync_error: Optional[str] = None
    sync_last_datetime: Optional[datetime] = None

    create_datetime: datetime
    last_update_datetime: datetime

    creator_uuid: Optional[uuid_pkg.UUID] = None

    cipher_credentials_private_repository: strawberry.Private[object]
    branches: list[str]


@strawberry.type()
class RepositoriesRegistryResultType(TypeInputMixin):
    count: int
    repositories_registry: list[RepositoryRegistryType] = field(default_factory=list)


@strawberry.type()
class CredentialsType(TypeInputMixin):
    username: str
    pat_token: str


@strawberry.type()
class OneRepositoryRegistryCredentialsType(TypeInputMixin):
    credentials: CredentialsType
    status: CredentialStatus
