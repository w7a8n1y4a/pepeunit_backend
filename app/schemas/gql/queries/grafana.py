import uuid as uuid_pkg

import strawberry
from strawberry.types import Info

from app.configs.gql import get_grafana_service_gql
from app.schemas.gql.inputs.grafana import DashboardFilterInput
from app.schemas.gql.types.grafana import (
    DashboardPanelsResultType,
    DashboardsResultType,
    DashboardType,
)


@strawberry.field()
def get_dashboard(uuid: uuid_pkg.UUID, info: Info) -> DashboardType:
    grafana_service = get_grafana_service_gql(info)
    return DashboardType(**grafana_service.get_dashboard(uuid).dict())


@strawberry.field()
def get_dashboards(filters: DashboardFilterInput, info: Info) -> DashboardsResultType:
    grafana_service = get_grafana_service_gql(info)
    count, dashboards = grafana_service.list_dashboards(filters)
    return DashboardsResultType(
        count=count,
        dashboards=[DashboardType(**dashboard.dict()) for dashboard in dashboards],
    )


@strawberry.field()
def get_dashboard_panels(uuid: uuid_pkg.UUID, info: Info) -> DashboardPanelsResultType:
    grafana_service = get_grafana_service_gql(info)
    panels = grafana_service.get_dashboard_panels(uuid)
    return DashboardPanelsResultType(
        count=panels.count,
        panels=[grafana_service.mapper_panel_to_type(panel) for panel in panels.panels],
    )
