import uuid as uuid_pkg
from datetime import datetime
from typing import Optional

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

    is_auto_update_repo: bool
    update_frequency_in_seconds: Optional[int] = 86400


@strawberry.input()
class RepoUpdateInput(TypeInputMixin):
    visibility_level: VisibilityLevel
    name: str

    is_public_repository: bool

    is_auto_update_repo: bool
    update_frequency_in_seconds: int


@strawberry.input()
class RepoFilterInput(TypeInputMixin):
    creator_uuid: Optional[str] = None
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
    """Фильтр выборки коммитов"""

    repo_branch: str

    offset: Optional[int] = 0
    limit: Optional[int] = 10
