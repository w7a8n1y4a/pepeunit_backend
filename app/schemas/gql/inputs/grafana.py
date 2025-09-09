import uuid as uuid_pkg
from typing import Optional

import strawberry

from app.dto.enum import DashboardPanelTypeEnum, OrderByDate
from app.schemas.gql.type_input_mixin import TypeInputMixin


@strawberry.input()
class DashboardCreateInput(TypeInputMixin):
    name: str


@strawberry.input()
class DashboardPanelCreateInput(TypeInputMixin):
    dashboard_uuid: uuid_pkg.UUID

    title: str
    type: DashboardPanelTypeEnum


@strawberry.input()
class LinkUnitNodeToPanelInput(TypeInputMixin):
    unit_node_uuid: uuid_pkg.UUID
    dashboard_panels_uuid: uuid_pkg.UUID
    is_last_data: bool
    is_forced_to_json: bool


@strawberry.input()
class DashboardFilterInput(TypeInputMixin):
    search_string: Optional[str] = None

    order_by_create_date: Optional[OrderByDate] = OrderByDate.desc

    offset: Optional[int] = None
    limit: Optional[int] = None
