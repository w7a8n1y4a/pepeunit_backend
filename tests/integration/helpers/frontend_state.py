import asyncio
import logging

from app import settings
from app.schemas.pydantic.grafana import DashboardFilter
from tests.integration.helpers.data_pipe import seed_pipe_node
from tests.integration.helpers.names import (
    REGULAR_USER_PASSWORD,
    entity_name,
)
from tests.integration.helpers.services import (
    grafana_service,
    token_for,
    unit_node_service,
)


async def _refill_and_sync_demo_dashboard(database, cc, token) -> None:
    grafana = grafana_service(database, cc, token)
    node_svc = unit_node_service(database, cc, token)
    _, dashboards = grafana.list_dashboards(
        DashboardFilter(search_string=entity_name("test0"))
    )
    if not dashboards:
        return

    dashboard = dashboards[0]
    panels = grafana.get_dashboard_panels(dashboard.uuid)
    for panel in panels.panels:
        for linked in panel.unit_nodes_for_panel:
            node = node_svc.get(uuid=linked.unit_node.uuid)
            await seed_pipe_node(node_svc, node, force=False)

    await grafana.sync_dashboard(dashboard.uuid)


def preserve_demo_dashboard(database, cc) -> None:
    """Keep the grafana test0 dashboard usable in the frontend after a run
    with PU_TEST_INTEGRATION_CLEAR_DATA=False.
    """
    if settings.pu_test_integration_clear_data:
        return
    if not settings.pu_ff_grafana_integration_enable:
        return

    try:
        token = token_for(
            database, cc, entity_name("regular"), REGULAR_USER_PASSWORD
        )
    except Exception:
        return

    try:
        asyncio.run(_refill_and_sync_demo_dashboard(database, cc, token))
    except Exception:
        logging.exception("failed to preserve the demo grafana dashboard")
