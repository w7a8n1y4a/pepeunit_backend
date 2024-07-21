import uuid as uuid_pkg
from typing import Optional

import strawberry

from app.repositories.enum import VisibilityLevel, OrderByDate
from app.schemas.gql.type_input_mixin import TypeInputMixin


@strawberry.input()
class UnitCreateInput(TypeInputMixin):
    repo_uuid: uuid_pkg.UUID

    visibility_level: VisibilityLevel
    name: str

    is_auto_update_from_repo_unit: bool

    repo_branch: Optional[str] = None
    repo_commit: Optional[str] = None


@strawberry.input()
class UnitUpdateInput(TypeInputMixin):
    visibility_level: Optional[VisibilityLevel] = None
    name: Optional[str] = None

    is_auto_update_from_repo_unit: Optional[bool] = None

    repo_branch: Optional[str] = None
    repo_commit: Optional[str] = None


@strawberry.input()
class UnitFilterInput(TypeInputMixin):
    creator_uuid: Optional[str] = None
    repo_uuid: Optional[str] = None

    search_string: Optional[str] = None

    is_auto_update_from_repo_unit: Optional[bool] = None

    visibility_level: list[VisibilityLevel] = tuple([item for item in VisibilityLevel])

    order_by_create_date: Optional[OrderByDate] = OrderByDate.desc
    order_by_last_update: Optional[OrderByDate] = OrderByDate.desc

    offset: Optional[int] = None
    limit: Optional[int] = None
