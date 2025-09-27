import uuid as uuid_pkg

import strawberry

from app.dto.enum import GitPlatform, OrderByDate
from app.schemas.gql.type_input_mixin import TypeInputMixin


@strawberry.input()
class CredentialsInput(TypeInputMixin):
    username: str
    pat_token: str


@strawberry.input()
class RepositoryRegistryCreateInput(TypeInputMixin):
    platform: GitPlatform
    repository_url: str

    is_public_repository: bool
    credentials: CredentialsInput | None = None


@strawberry.input()
class CommitFilterInput(TypeInputMixin):
    repo_branch: str
    only_tag: bool = False

    offset: int | None = 0
    limit: int | None = 10


@strawberry.input()
class RepositoryRegistryFilterInput(TypeInputMixin):
    uuids: list[uuid_pkg.UUID] | None = ()

    creator_uuid: uuid_pkg.UUID | None = None
    search_string: str | None = None

    is_public_repository: bool | None = None

    order_by_create_date: OrderByDate | None = OrderByDate.desc
    order_by_last_update: OrderByDate | None = OrderByDate.desc

    offset: int | None = None
    limit: int | None = None
