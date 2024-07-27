from typing import Optional
import uuid as uuid_pkg

import strawberry

from app.repositories.enum import OrderByDate, VisibilityLevel
from app.schemas.gql.type_input_mixin import TypeInputMixin


@strawberry.input()
class CredentialsInput(TypeInputMixin):
    username: str
    pat_token: str


@strawberry.input()
class RepoCreateInput(TypeInputMixin):
    visibility_level: VisibilityLevel
    name: str

    repo_url: str

    is_public_repository: bool
    credentials: Optional[CredentialsInput] = None


@strawberry.input()
class RepoUpdateInput(TypeInputMixin):
    visibility_level: Optional[VisibilityLevel] = None
    name: Optional[str] = None

    is_auto_update_repo: Optional[bool] = None

    default_branch: Optional[str] = None
    default_commit: Optional[str] = None

    is_only_tag_update: Optional[bool] = None
    update_frequency_in_seconds: Optional[int] = None


@strawberry.input()
class RepoFilterInput(TypeInputMixin):
    creator_uuid: Optional[uuid_pkg.UUID] = None
    search_string: Optional[str] = None

    is_public_repository: Optional[bool] = None
    is_auto_update_repo: Optional[bool] = None

    visibility_level: list[VisibilityLevel] = tuple([item for item in VisibilityLevel])

    order_by_create_date: Optional[OrderByDate] = OrderByDate.desc
    order_by_last_update: Optional[OrderByDate] = OrderByDate.desc

    offset: Optional[int] = None
    limit: Optional[int] = None


@strawberry.input()
class CommitFilterInput(TypeInputMixin):
    repo_branch: str

    offset: Optional[int] = 0
    limit: Optional[int] = 10
