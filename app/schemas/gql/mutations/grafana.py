import uuid as uuid_pkg

import strawberry
from strawberry.types import Info

from app.configs.gql import get_grafana_service_gql
from app.schemas.gql.inputs.grafana import (
    DashboardCreateInput,
    DashboardPanelCreateInput,
    LinkUnitNodeToPanelInput,
)
from app.schemas.gql.types.grafana import (
    DashboardPanelType,
    DashboardType,
    UnitNodeForPanelType,
)
from app.schemas.gql.types.shared import NoneType


@strawberry.mutation()
def create_dashboard(info: Info, dashboard: DashboardCreateInput) -> DashboardType:
    grafana_service = get_grafana_service_gql(info)
    return DashboardType(**grafana_service.create_dashboard(dashboard).dict())


@strawberry.mutation()
def create_dashboard_panel(
    info: Info, dashboard_panel: DashboardPanelCreateInput
) -> DashboardPanelType:
    grafana_service = get_grafana_service_gql(info)
    return DashboardPanelType(
        unit_nodes_for_panel=[],
        **grafana_service.create_dashboard_panel(dashboard_panel).dict(),
    )


@strawberry.mutation()
def link_unit_node_to_panel(
    info: Info, dashboard: LinkUnitNodeToPanelInput
) -> UnitNodeForPanelType:
    grafana_service = get_grafana_service_gql(info)
    return grafana_service.mapper_unit_nodes_to_type(
        grafana_service.link_unit_node_to_panel(dashboard)
    )


@strawberry.mutation()
async def sync_dashboard(info: Info, uuid: uuid_pkg.UUID) -> DashboardType:
    grafana_service = get_grafana_service_gql(info)
    return DashboardType(**(await grafana_service.sync_dashboard(uuid)).dict())


@strawberry.mutation()
def delete_dashboard(info: Info, uuid: uuid_pkg.UUID) -> NoneType:
    grafana_service = get_grafana_service_gql(info)
    grafana_service.delete_dashboard(uuid)
    return NoneType()


@strawberry.mutation()
def delete_panel(info: Info, uuid: uuid_pkg.UUID) -> NoneType:
    grafana_service = get_grafana_service_gql(info)
    grafana_service.delete_panel(uuid)
    return NoneType()


@strawberry.mutation()
def delete_link(
    info: Info, unit_node_uuid: uuid_pkg.UUID, dashboard_panel_uuid: uuid_pkg.UUID
) -> NoneType:
    grafana_service = get_grafana_service_gql(info)
    grafana_service.delete_link(unit_node_uuid, dashboard_panel_uuid)
    return NoneType()
