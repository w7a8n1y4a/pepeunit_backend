import uuid as uuid_pkg
from datetime import datetime

import strawberry
from strawberry import field

from app.dto.enum import DashboardPanelTypeEnum, DashboardStatus
from app.schemas.gql.type_input_mixin import TypeInputMixin
from app.schemas.gql.types.shared import UnitNodeType


@strawberry.type()
class DashboardType(TypeInputMixin):
    uuid: uuid_pkg.UUID
    grafana_uuid: uuid_pkg.UUID

    name: str
    create_datetime: datetime

    dashboard_url: str | None = None
    inc_last_version: int | None = None

    sync_status: DashboardStatus | None = None
    sync_error: str | None = None
    sync_last_datetime: datetime | None = None

    creator_uuid: uuid_pkg.UUID


@strawberry.type()
class UnitNodeForPanelType(TypeInputMixin):
    unit_node: UnitNodeType
    is_last_data: bool
    is_forced_to_json: bool
    unit_with_unit_node_name: str


@strawberry.type()
class DashboardPanelType(TypeInputMixin):
    uuid: uuid_pkg.UUID

    type: DashboardPanelTypeEnum

    title: str
    create_datetime: datetime

    creator_uuid: uuid_pkg.UUID
    dashboard_uuid: uuid_pkg.UUID

    unit_nodes_for_panel: list[UnitNodeForPanelType]


@strawberry.type()
class DashboardsResultType(TypeInputMixin):
    count: int
    dashboards: list[DashboardType] = field(default_factory=list)


@strawberry.type()
class DashboardPanelsResultType(TypeInputMixin):
    count: int
    panels: list[DashboardPanelType] = field(default_factory=list)
