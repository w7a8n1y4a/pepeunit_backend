import uuid as uuid_pkg
from typing import Optional

import strawberry

from app.dto.enum import GitPlatform, OrderByDate, VisibilityLevel
from app.schemas.gql.type_input_mixin import TypeInputMixin


@strawberry.input()
class RepoCreateInput(TypeInputMixin):
    repository_registry_uuid: uuid_pkg.UUID

    visibility_level: VisibilityLevel
    name: str

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
    repository_registry_uuid: Optional[uuid_pkg.UUID] = None

    uuids: Optional[list[uuid_pkg.UUID]] = tuple()

    creator_uuid: Optional[uuid_pkg.UUID] = None
    creators_uuids: Optional[list[uuid_pkg.UUID]] = tuple()
    search_string: Optional[str] = None

    is_auto_update_repo: Optional[bool] = None

    visibility_level: Optional[list[VisibilityLevel]] = tuple([item for item in VisibilityLevel])

    order_by_create_date: Optional[OrderByDate] = OrderByDate.desc
    order_by_last_update: Optional[OrderByDate] = OrderByDate.desc

    offset: Optional[int] = None
    limit: Optional[int] = None
