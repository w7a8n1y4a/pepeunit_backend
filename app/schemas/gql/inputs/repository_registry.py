import uuid as uuid_pkg
from typing import Optional

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
    credentials: Optional[CredentialsInput] = None


@strawberry.input()
class CommitFilterInput(TypeInputMixin):
    repo_branch: str
    only_tag: bool = False

    offset: Optional[int] = 0
    limit: Optional[int] = 10


@strawberry.input()
class RepositoryRegistryFilterInput(TypeInputMixin):
    uuids: Optional[list[uuid_pkg.UUID]] = tuple()

    creator_uuid: Optional[uuid_pkg.UUID] = None
    search_string: Optional[str] = None

    is_public_repository: Optional[bool] = None

    order_by_create_date: Optional[OrderByDate] = OrderByDate.desc
    order_by_last_update: Optional[OrderByDate] = OrderByDate.desc

    offset: Optional[int] = None
    limit: Optional[int] = None
