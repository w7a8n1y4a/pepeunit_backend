import pytest

from app import settings
from app.dto.enum import DashboardPanelTypeEnum
from app.schemas.pydantic.grafana import DashboardCreate, DashboardPanelCreate
from tests.integration.helpers.names import entity_name
from tests.integration.helpers.services import grafana_service


def _delete_dashboard(service, uuid) -> None:
    try:
        service.delete_dashboard(uuid=uuid)
    except Exception:
        pass


@pytest.fixture(scope="module")
def grafana_dashboards(regular_user_token, database, cc):
    service = grafana_service(database, cc, regular_user_token)
    first = service.create_dashboard(DashboardCreate(name=entity_name("test0")))
    second = service.create_dashboard(DashboardCreate(name=entity_name("test1")))
    yield first, second
    _delete_dashboard(service, second.uuid)
    # first dashboard has all panel types + pipe links; leave it for the
    # frontend when PU_TEST_INTEGRATION_CLEAR_DATA=False
    if settings.pu_test_integration_clear_data:
        _delete_dashboard(service, first.uuid)


@pytest.fixture(scope="module")
def grafana_panels(grafana_dashboards, regular_user_token, database, cc):
    service = grafana_service(database, cc, regular_user_token)
    dashboard, delete_dashboard = grafana_dashboards
    panels = []
    for target_type in (
        DashboardPanelTypeEnum.HOURLY_HEATMAP,
        DashboardPanelTypeEnum.PIE_CHART,
        DashboardPanelTypeEnum.TIME_SERIES,
        DashboardPanelTypeEnum.LOGS,
    ):
        panels.append(
            service.create_dashboard_panel(
                DashboardPanelCreate(
                    dashboard_uuid=dashboard.uuid,
                    title=str(target_type.value)[:15],
                    type=target_type,
                )
            )
        )

    delete_panel = service.create_dashboard_panel(
        DashboardPanelCreate(
            dashboard_uuid=delete_dashboard.uuid,
            title="BestChart",
            type=DashboardPanelTypeEnum.TIME_SERIES,
        )
    )
    yield panels, delete_panel
    try:
        service.delete_panel(uuid=delete_panel.uuid)
    except Exception:
        pass
