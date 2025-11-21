import uuid as uuid_pkg

import strawberry

from app.dto.enum import OrderByDate, VisibilityLevel
from app.schemas.gql.type_input_mixin import BasePaginationGql, TypeInputMixin


@strawberry.input()
class RepoCreateInput(TypeInputMixin):
    repository_registry_uuid: uuid_pkg.UUID
    default_branch: str

    visibility_level: VisibilityLevel
    name: str

    is_compilable_repo: bool


@strawberry.input()
class RepoUpdateInput(TypeInputMixin):
    visibility_level: VisibilityLevel | None = None
    name: str | None = None

    is_auto_update_repo: bool | None = None

    default_branch: str | None = None
    default_commit: str | None = None

    is_only_tag_update: bool | None = None

    is_compilable_repo: bool | None = None


@strawberry.input()
class RepoFilterInput(BasePaginationGql):
    repository_registry_uuid: uuid_pkg.UUID | None = None

    uuids: list[uuid_pkg.UUID] | None = ()

    creator_uuid: uuid_pkg.UUID | None = None
    creators_uuids: list[uuid_pkg.UUID] | None = ()
    search_string: str | None = None

    is_auto_update_repo: bool | None = None

    visibility_level: list[VisibilityLevel] | None = tuple(VisibilityLevel)

    order_by_create_date: OrderByDate | None = OrderByDate.desc
    order_by_last_update: OrderByDate | None = OrderByDate.desc
