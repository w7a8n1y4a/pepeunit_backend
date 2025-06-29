import uuid as uuid_pkg
from typing import Optional

import strawberry

from app.dto.enum import GitPlatform, OrderByDate, VisibilityLevel
from app.schemas.gql.type_input_mixin import TypeInputMixin


@strawberry.input()
class CredentialsInput(TypeInputMixin):
    username: str
    pat_token: str


@strawberry.input()
class RepoCreateInput(TypeInputMixin):
    visibility_level: VisibilityLevel
    name: str

    repository_url: str
    platform: GitPlatform

    is_public_repository: bool
    credentials: Optional[CredentialsInput] = None

    is_compilable_repo: bool


@strawberry.input()
class RepoUpdateInput(TypeInputMixin):
    visibility_level: Optional[VisibilityLevel] = None
    name: Optional[str] = None

    is_auto_update_repo: Optional[bool] = None

    default_branch: Optional[str] = None
    default_commit: Optional[str] = None

    is_only_tag_update: Optional[bool] = None

    is_compilable_repo: Optional[bool] = None


@strawberry.input()
class RepoFilterInput(TypeInputMixin):
    uuids: Optional[list[uuid_pkg.UUID]] = tuple()

    creator_uuid: Optional[uuid_pkg.UUID] = None
    creators_uuids: Optional[list[uuid_pkg.UUID]] = tuple()
    search_string: Optional[str] = None

    is_public_repository: Optional[bool] = None
    is_auto_update_repo: Optional[bool] = None

    visibility_level: Optional[list[VisibilityLevel]] = tuple([item for item in VisibilityLevel])

    order_by_create_date: Optional[OrderByDate] = OrderByDate.desc
    order_by_last_update: Optional[OrderByDate] = OrderByDate.desc

    offset: Optional[int] = None
    limit: Optional[int] = None


@strawberry.input()
class CommitFilterInput(TypeInputMixin):
    repo_branch: str
    only_tag: bool = False

    offset: Optional[int] = 0
    limit: Optional[int] = 10
