import uuid as uuid_pkg
from typing import Optional

import strawberry

from app.repositories.enum import OrderByDate, OrderByText, UnitNodeTypeEnum, VisibilityLevel
from app.schemas.gql.type_input_mixin import TypeInputMixin


@strawberry.input()
class UnitNodeUpdateInput(TypeInputMixin):
    visibility_level: Optional[VisibilityLevel] = None
    is_rewritable_input: Optional[bool] = None


@strawberry.input()
class UnitNodeSetStateInput(TypeInputMixin):
    state: Optional[str] = None


@strawberry.input()
class UnitNodeFilterInput(TypeInputMixin):
    uuids: Optional[list[uuid_pkg.UUID]] = tuple()

    # get only input for this output node
    output_uuid: Optional[uuid_pkg.UUID] = None

    unit_uuid: Optional[uuid_pkg.UUID] = None
    search_string: Optional[str] = None

    type: Optional[list[UnitNodeTypeEnum]] = tuple([item for item in UnitNodeTypeEnum])
    visibility_level: Optional[list[VisibilityLevel]] = tuple([item for item in VisibilityLevel])

    order_by_create_date: Optional[OrderByDate] = OrderByDate.desc

    offset: Optional[int] = None
    limit: Optional[int] = None


@strawberry.input()
class UnitNodeEdgeCreateInput(TypeInputMixin):
    node_output_uuid: uuid_pkg.UUID
    node_input_uuid: uuid_pkg.UUID
