from typing import Optional

import strawberry

from app.repositories.enum import OrderByDate, UnitNodeTypeEnum, VisibilityLevel
from app.schemas.gql.type_input_mixin import TypeInputMixin


@strawberry.input()
class UnitNodeUpdateInput(TypeInputMixin):
    visibility_level: VisibilityLevel
    is_rewritable_input: bool


@strawberry.input()
class UnitNodeSetStateInput(TypeInputMixin):
    state: Optional[str] = None


@strawberry.input()
class UnitNodeFilterInput(TypeInputMixin):
    search_string: Optional[str] = None

    type: Optional[UnitNodeTypeEnum] = None
    visibility_level: Optional[VisibilityLevel] = None

    order_by_create_date: Optional[OrderByDate] = OrderByDate.desc

    offset: Optional[int] = None
    limit: Optional[int] = None
