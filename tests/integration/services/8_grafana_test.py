import csv
import datetime
import json
import logging
import os
import random
from io import StringIO

import pytest
from fastapi import UploadFile

from app import settings
from app.configs.errors import GrafanaError, NoAccessError
from app.dto.agent.abc import AgentGrafanaUnitNode
from app.dto.enum import (
    DashboardPanelTypeEnum,
    DashboardStatus,
    DatasourceFormat,
    ProcessingPolicyType,
    UnitNodeTypeEnum,
)
from app.schemas.pydantic.grafana import (
    DashboardCreate,
    DashboardFilter,
    DashboardPanelCreate,
    DatasourceFilter,
    LinkUnitNodeToPanel,
)
from app.schemas.pydantic.unit_node import DataPipeFilter, UnitNodeFilter
from app.validators.data_pipe import is_valid_data_pipe_config
from tests.integration.helpers.names import unique_name
from tests.integration.helpers.services import (
    grafana_service,
    unit_node_service,
    user_service,
)


@pytest.mark.grafana
def test_create_dashboard(grafana_dashboards, regular_user_token, database, cc) -> None:
    first, second = grafana_dashboards
    assert first.uuid
    assert second.uuid

    service = grafana_service(database, cc, regular_user_token)
    with pytest.raises(GrafanaError):
        service.create_dashboard(DashboardCreate(name="x"))


@pytest.mark.grafana
def test_create_dashboard_panel(
    grafana_panels, grafana_dashboards, regular_user_token, database, cc
) -> None:
    panels, delete_panel = grafana_panels
    assert len(panels) == 4
    assert delete_panel.uuid

    service = grafana_service(database, cc, regular_user_token)
    with pytest.raises(GrafanaError):
        service.create_dashboard_panel(
            DashboardPanelCreate(
                dashboard_uuid=grafana_dashboards[0].uuid,
                title="x",
                type=DashboardPanelTypeEnum.PIE_CHART,
            )
        )


@pytest.mark.grafana
@pytest.mark.datapipe
async def test_import_data_to_data_pipe(
    piped_units,
    regular_user_token,
    database,
    cc,
) -> None:
    service = unit_node_service(database, cc, regular_user_token)
    os.makedirs("tmp/csv", exist_ok=True)

    def save_csv_to_file(filepath: str, data: list[dict]) -> None:
        if not data:
            raise Exception("No data found")
        csv_data = StringIO()
        writer = csv.writer(csv_data)
        writer.writerow(data[0].keys())
        for item in data:
            writer.writerow(item.values())
        with open(filepath, "w") as handle:
            handle.write(csv_data.getvalue())

    csv_save_paths = {
        ProcessingPolicyType.AGGREGATION: "tmp/csv/aggregation.csv",
        ProcessingPolicyType.N_RECORDS: "tmp/csv/n_records.csv",
        ProcessingPolicyType.TIME_WINDOW: "tmp/csv/time_window.csv",
    }

    def generation_csv_for_policy(policy: ProcessingPolicyType) -> None:
        data = []
        now = datetime.datetime.now(datetime.UTC).replace(
            tzinfo=None, second=0, microsecond=0
        )
        match policy:
            case ProcessingPolicyType.AGGREGATION:
                step = datetime.timedelta(minutes=1)
                for i in range(2000):
                    end_window = now - i * step
                    start_window = end_window - datetime.timedelta(seconds=60)
                    data.append(
                        {
                            "state": round(random.uniform(-20.0, 10.0), 2),
                            "create_datetime": end_window,
                            "start_window_datetime": start_window,
                            "end_window_datetime": end_window,
                        }
                    )
            case ProcessingPolicyType.N_RECORDS:
                step = datetime.timedelta(minutes=60)
                for i in range(100):
                    data.append(
                        {
                            "state": round(random.uniform(1, 10.0), 2),
                            "create_datetime": now - i * step,
                        }
                    )
            case ProcessingPolicyType.TIME_WINDOW:
                step = datetime.timedelta(seconds=2)
                for i in range(100):
                    data.append(
                        {
                            "state": json.dumps(
                                {
                                    "level": random.choice(["error", "info", "warning"]),
                                    "TitleMessage": random.choice(
                                        ["Test Info One", "Test Info Two"]
                                    ),
                                }
                            ),
                            "create_datetime": now - i * step,
                        }
                    )
        data.sort(key=lambda item: item["create_datetime"])
        save_csv_to_file(csv_save_paths[policy], data)

    for unit in piped_units.piped():
        count, input_unit_node = service.list(
            UnitNodeFilter(unit_uuid=unit.uuid, type=[UnitNodeTypeEnum.INPUT])
        )
        data_pipe_entity = is_valid_data_pipe_config(
            json.loads(input_unit_node[0].data_pipe_yml), is_business_validator=True
        )
        logging.info(data_pipe_entity.processing_policy.policy_type)
        if data_pipe_entity.processing_policy.policy_type != ProcessingPolicyType.LAST_VALUE:
            generation_csv_for_policy(data_pipe_entity.processing_policy.policy_type)
            await service.set_data_pipe_data_csv(
                uuid=input_unit_node[0].uuid,
                data_csv=UploadFile(
                    filename="",
                    file=open(
                        csv_save_paths[data_pipe_entity.processing_policy.policy_type],
                        "rb",
                    ),
                ),
            )
        else:
            service.set_state(
                unit_node_uuid=input_unit_node[0].uuid,
                state=json.dumps({"one": 5, "two": 10, "three": 20}),
            )


@pytest.mark.grafana
@pytest.mark.datapipe
def test_create_link_unit_node_to_panel(
    grafana_panels,
    piped_units,
    regular_user_token,
    database,
    cc,
) -> None:
    service = unit_node_service(database, cc, regular_user_token)
    grafana = grafana_service(database, cc, regular_user_token)
    panels, delete_panel = grafana_panels

    for target_type, unit, panel in zip(
        [
            DashboardPanelTypeEnum.HOURLY_HEATMAP,
            DashboardPanelTypeEnum.PIE_CHART,
            DashboardPanelTypeEnum.TIME_SERIES,
            DashboardPanelTypeEnum.LOGS,
        ],
        piped_units.piped(),
        panels,
        strict=False,
    ):
        count, input_unit_node = service.list(
            UnitNodeFilter(unit_uuid=unit.uuid, type=[UnitNodeTypeEnum.INPUT])
        )
        data_pipe_entity = is_valid_data_pipe_config(
            json.loads(input_unit_node[0].data_pipe_yml), is_business_validator=True
        )
        logging.info(
            f"{target_type} {input_unit_node[0].uuid}-{data_pipe_entity.processing_policy.policy_type} {panel.uuid}-{panel.type}"
        )
        grafana.link_unit_node_to_panel(
            LinkUnitNodeToPanel(
                unit_node_uuid=input_unit_node[0].uuid,
                dashboard_panels_uuid=panel.uuid,
                is_forced_to_json=target_type
                in [DashboardPanelTypeEnum.PIE_CHART, DashboardPanelTypeEnum.LOGS],
                is_last_data=False,
            )
        )
        with pytest.raises(GrafanaError):
            grafana.link_unit_node_to_panel(
                LinkUnitNodeToPanel(
                    unit_node_uuid=input_unit_node[0].uuid,
                    dashboard_panels_uuid=panel.uuid,
                    is_forced_to_json=target_type == DashboardPanelTypeEnum.PIE_CHART,
                    is_last_data=False,
                )
            )

    count, input_unit_node = service.list(
        UnitNodeFilter(
            unit_uuid=piped_units.universal_manual_unit.uuid,
            type=[UnitNodeTypeEnum.INPUT],
        )
    )
    grafana.link_unit_node_to_panel(
        LinkUnitNodeToPanel(
            unit_node_uuid=input_unit_node[0].uuid,
            dashboard_panels_uuid=delete_panel.uuid,
            is_forced_to_json=False,
            is_last_data=False,
        )
    )


@pytest.mark.grafana
@pytest.mark.datapipe
def test_get_aggregation_pipe_data_after_import(
    grafana_panels,
    piped_units,
    regular_user_token,
    database,
    cc,
) -> None:
    service = unit_node_service(database, cc, regular_user_token)
    _, input_nodes = service.list(
        UnitNodeFilter(
            unit_uuid=piped_units.universal_manual_unit.uuid,
            type=[UnitNodeTypeEnum.INPUT],
        )
    )
    count, rows = service.get_data_pipe_data(
        DataPipeFilter(
            uuid=input_nodes[0].uuid, type=ProcessingPolicyType.AGGREGATION
        )
    )
    assert count > 0
    assert rows


@pytest.mark.grafana
@pytest.mark.datapipe
def test_grafana_datasource_data(
    grafana_panels,
    piped_units,
    regular_user_token,
    database,
    cc,
) -> None:
    node_svc = unit_node_service(database, cc, regular_user_token)
    panels, _ = grafana_panels
    _, input_nodes = node_svc.list(
        UnitNodeFilter(
            unit_uuid=piped_units.universal_manual_unit.uuid,
            type=[UnitNodeTypeEnum.INPUT],
        )
    )
    token = AgentGrafanaUnitNode(
        uuid=input_nodes[0].uuid,
        panel_uuid=panels[0].uuid,
        name="grafana",
    ).generate_agent_token()
    data = grafana_service(database, cc, token).get_datasource_data(
        DatasourceFilter(format=DatasourceFormat.TIME_SERIES)
    )
    assert data
    assert data[0].time is not None

    with pytest.raises(NoAccessError):
        grafana_service(
            database, cc, regular_user_token
        ).get_datasource_data(
            DatasourceFilter(format=DatasourceFormat.TIME_SERIES)
        )


@pytest.mark.grafana
def test_create_org_if_not_exists(
    regular_user, regular_user_token, database, cc
) -> None:
    service = user_service(database, cc, regular_user_token)
    service.create_org_if_not_exists(regular_user.uuid)
    assert service.get(regular_user.uuid).grafana_org_id


@pytest.mark.grafana
def test_panel_unit_node_limit(
    live_units, regular_user_token, database, cc
) -> None:
    grafana = grafana_service(database, cc, regular_user_token)
    node_svc = unit_node_service(database, cc, regular_user_token)
    dashboard = grafana.create_dashboard(
        DashboardCreate(name=unique_name("gflim"))
    )
    panel = grafana.create_dashboard_panel(
        DashboardPanelCreate(
            dashboard_uuid=dashboard.uuid,
            title="LimitPanel",
            type=DashboardPanelTypeEnum.TIME_SERIES,
        )
    )
    nodes = []
    for unit in live_units.all():
        _, unit_nodes = node_svc.list(
            UnitNodeFilter(
                unit_uuid=unit.uuid,
                type=[item.value for item in UnitNodeTypeEnum],
                offset=0,
                limit=settings.pu_max_pagination_size,
            )
        )
        nodes.extend(unit_nodes)
    limit = settings.pu_grafana_limit_unit_node_per_one_panel
    assert len(nodes) > limit
    try:
        for node in nodes[:limit]:
            grafana.link_unit_node_to_panel(
                LinkUnitNodeToPanel(
                    unit_node_uuid=node.uuid,
                    dashboard_panels_uuid=panel.uuid,
                    is_forced_to_json=False,
                    is_last_data=False,
                )
            )
        with pytest.raises(GrafanaError):
            grafana.link_unit_node_to_panel(
                LinkUnitNodeToPanel(
                    unit_node_uuid=nodes[limit].uuid,
                    dashboard_panels_uuid=panel.uuid,
                    is_forced_to_json=False,
                    is_last_data=False,
                )
            )
    finally:
        grafana.delete_dashboard(dashboard.uuid)


@pytest.mark.grafana
async def test_sync_dashboard(
    grafana_dashboards, regular_user_token, database, cc
) -> None:
    service = grafana_service(database, cc, regular_user_token)
    dashboard = await service.sync_dashboard(grafana_dashboards[0].uuid)
    assert dashboard.sync_status == DashboardStatus.SUCCESS


@pytest.mark.grafana
def test_get_dashboard(grafana_dashboards, regular_user_token, database, cc) -> None:
    grafana_service(database, cc, regular_user_token).get_dashboard(
        grafana_dashboards[0].uuid
    )


@pytest.mark.grafana
def test_list_dashboards(grafana_dashboards, regular_user_token, database, cc) -> None:
    count, dashboards = grafana_service(
        database, cc, regular_user_token
    ).list_dashboards(DashboardFilter(search_string="test", offset=0, limit=10))
    assert count >= 2


@pytest.mark.grafana
def test_get_dashboard_panels(
    grafana_panels, grafana_dashboards, regular_user_token, database, cc
) -> None:
    panels = grafana_service(database, cc, regular_user_token).get_dashboard_panels(
        grafana_dashboards[0].uuid
    )
    assert panels.count >= 4


@pytest.mark.grafana
@pytest.mark.datapipe
def test_delete_link(
    grafana_panels,
    piped_units,
    regular_user_token,
    database,
    cc,
) -> None:
    service = unit_node_service(database, cc, regular_user_token)
    grafana = grafana_service(database, cc, regular_user_token)
    _, delete_panel = grafana_panels
    count, input_unit_node = service.list(
        UnitNodeFilter(
            unit_uuid=piped_units.universal_manual_unit.uuid,
            type=[UnitNodeTypeEnum.INPUT],
        )
    )
    grafana.delete_link(
        unit_node_uuid=input_unit_node[0].uuid,
        dashboard_panel_uuid=delete_panel.uuid,
    )


@pytest.mark.grafana
def test_delete_panel(grafana_panels, regular_user_token, database, cc) -> None:
    _, delete_panel = grafana_panels
    grafana_service(database, cc, regular_user_token).delete_panel(uuid=delete_panel.uuid)


@pytest.mark.grafana
def test_delete_dashboard(grafana_dashboards, regular_user_token, database, cc) -> None:
    grafana_service(database, cc, regular_user_token).delete_dashboard(
        uuid=grafana_dashboards[1].uuid
    )
