import csv
import datetime
import json
import logging
import random
from io import StringIO

import pytest
from fastapi import UploadFile

from app.configs.errors import GrafanaError
from app.configs.rest import get_grafana_service, get_unit_node_service
from app.dto.enum import DashboardPanelTypeEnum, DashboardStatus, ProcessingPolicyType, UnitNodeTypeEnum
from app.schemas.pydantic.grafana import DashboardCreate, DashboardFilter, DashboardPanelCreate, LinkUnitNodeToPanel
from app.schemas.pydantic.unit_node import UnitNodeFilter
from app.validators.data_pipe import is_valid_data_pipe_config


@pytest.mark.run(order=0)
def test_emulator_stop(client_emulator):
    client_emulator.task_queue.put("STOP")


@pytest.mark.run(order=1)
def test_create_dashboard(test_dashboards, database, cc) -> None:

    current_user = pytest.users[0]
    grafana_service = get_grafana_service(database, cc, pytest.user_tokens_dict[current_user.uuid])

    # check create
    new_dashboards = []
    for test_dashboard in test_dashboards:
        dashboard = grafana_service.create_dashboard(
            DashboardCreate(
                name=test_dashboard,
            )
        )

        new_dashboards.append(dashboard)

    assert len(new_dashboards) >= len(test_dashboards)

    pytest.dashboards = new_dashboards

    # check create with bad name
    with pytest.raises(GrafanaError):
        grafana_service.create_dashboard(DashboardCreate(name='x'))


@pytest.mark.run(order=2)
def test_create_dashboard_panel(database, cc) -> None:

    current_user = pytest.users[0]
    grafana_service = get_grafana_service(database, cc, pytest.user_tokens_dict[current_user.uuid])

    # check create
    new_dashboard_panels = []
    for target_type in [
        DashboardPanelTypeEnum.HOURLY_HEATMAP,
        DashboardPanelTypeEnum.PIE_CHART,
        DashboardPanelTypeEnum.TIME_SERIES,
        DashboardPanelTypeEnum.LOGS,
    ]:
        panel = grafana_service.create_dashboard_panel(
            DashboardPanelCreate(
                dashboard_uuid=pytest.dashboards[0].uuid, title=str(target_type.value)[:15], type=target_type
            )
        )

        new_dashboard_panels.append(panel)

    pytest.panels = new_dashboard_panels

    # check create with bad name
    with pytest.raises(GrafanaError):
        grafana_service.create_dashboard_panel(
            DashboardPanelCreate(
                dashboard_uuid=pytest.dashboards[0].uuid, title='x', type=DashboardPanelTypeEnum.PIE_CHART
            )
        )

    # creation for future deletion
    panel = grafana_service.create_dashboard_panel(
        DashboardPanelCreate(
            dashboard_uuid=pytest.dashboards[1].uuid, title='BestChart', type=DashboardPanelTypeEnum.TIME_SERIES
        )
    )

    pytest.delete_panel = [panel]


@pytest.mark.run(order=3)
async def test_import_data_to_data_pipe(database, cc) -> None:
    current_user = pytest.users[0]
    unit_node_service = get_unit_node_service(database, cc, pytest.user_tokens_dict[current_user.uuid])

    def save_csv_to_file(filepath: str, data: list[dict]) -> None:

        if not len(data):
            raise Exception('No data found')

        csv_data = StringIO()
        writer = csv.writer(csv_data)
        writer.writerow(data[0].keys())
        for item in data:
            writer.writerow(item.values())

        result = csv_data.getvalue()

        with open(filepath, 'w') as f:
            f.write(result)

    csv_save_paths = {
        ProcessingPolicyType.AGGREGATION: 'tmp/csv/aggregation.csv',
        ProcessingPolicyType.N_RECORDS: 'tmp/csv/n_records.csv',
        ProcessingPolicyType.TIME_WINDOW: 'tmp/csv/time_window.csv',
    }

    def generation_csv_for_policy(policy: ProcessingPolicyType) -> None:

        data = []
        now = datetime.datetime.utcnow().replace(second=0, microsecond=0)
        match policy:
            case ProcessingPolicyType.AGGREGATION:
                step = datetime.timedelta(minutes=1)
                for i in range(2000):
                    end_window = now - i * step
                    start_window = end_window - datetime.timedelta(seconds=60)
                    record = {
                        "state": round(random.uniform(-20.0, 10.0), 2),
                        "create_datetime": end_window,
                        "start_window_datetime": start_window,
                        "end_window_datetime": end_window,
                    }
                    data.append(record)

            case ProcessingPolicyType.N_RECORDS:
                step = datetime.timedelta(minutes=60)
                for i in range(100):
                    create_datetime = now - i * step
                    record = {
                        "state": round(random.uniform(1, 10.0), 2),
                        "create_datetime": create_datetime,
                    }
                    data.append(record)
            case ProcessingPolicyType.TIME_WINDOW:
                step = datetime.timedelta(seconds=2)
                for i in range(100):
                    create_datetime = now - i * step
                    record = {
                        "state": json.dumps(
                            {
                                'level': random.choice(['error', 'info', 'warning']),
                                'TitleMessage': random.choice(['Test Info One', 'Test Info Two']),
                            }
                        ),
                        "create_datetime": create_datetime,
                    }
                    data.append(record)

        data.sort(key=lambda x: x["create_datetime"])
        save_csv_to_file(csv_save_paths[policy], data)

    # check create data all types
    for unit in pytest.units[1:5]:
        count, input_unit_node = unit_node_service.list(
            UnitNodeFilter(unit_uuid=unit.uuid, type=[UnitNodeTypeEnum.INPUT])
        )

        data_pipe_entity = is_valid_data_pipe_config(
            json.loads(input_unit_node[0].data_pipe_yml), is_business_validator=True
        )
        logging.info(data_pipe_entity.processing_policy.policy_type)
        if data_pipe_entity.processing_policy.policy_type != ProcessingPolicyType.LAST_VALUE:
            generation_csv_for_policy(data_pipe_entity.processing_policy.policy_type)

            await unit_node_service.set_data_pipe_data_csv(
                uuid=input_unit_node[0].uuid,
                data_csv=UploadFile(
                    filename='',
                    file=open(csv_save_paths[data_pipe_entity.processing_policy.policy_type], "rb"),
                ),
            )
        else:
            unit_node_service.set_state(
                unit_node_uuid=input_unit_node[0].uuid,
                state=json.dumps({'one': 5, 'two': 10, 'three': 20}),
            )


@pytest.mark.run(order=4)
def test_create_link_unit_node_to_panel(database, cc) -> None:

    current_user = pytest.users[0]
    unit_node_service = get_unit_node_service(database, cc, pytest.user_tokens_dict[current_user.uuid])
    grafana_service = get_grafana_service(database, cc, pytest.user_tokens_dict[current_user.uuid])

    # check create link
    for target_type, unit, panel in zip(
        [
            DashboardPanelTypeEnum.HOURLY_HEATMAP,
            DashboardPanelTypeEnum.PIE_CHART,
            DashboardPanelTypeEnum.TIME_SERIES,
            DashboardPanelTypeEnum.LOGS,
        ],
        pytest.units[1:5],
        pytest.panels,
    ):
        count, input_unit_node = unit_node_service.list(
            UnitNodeFilter(unit_uuid=unit.uuid, type=[UnitNodeTypeEnum.INPUT])
        )

        data_pipe_entity = is_valid_data_pipe_config(
            json.loads(input_unit_node[0].data_pipe_yml), is_business_validator=True
        )

        logging.info(
            f'{target_type} {input_unit_node[0].uuid}-{data_pipe_entity.processing_policy.policy_type} {panel.uuid}-{panel.type}'
        )

        grafana_service.link_unit_node_to_panel(
            LinkUnitNodeToPanel(
                unit_node_uuid=input_unit_node[0].uuid,
                dashboard_panels_uuid=panel.uuid,
                is_forced_to_json=(
                    True if target_type in [DashboardPanelTypeEnum.PIE_CHART, DashboardPanelTypeEnum.LOGS] else False
                ),
                is_last_data=False,
            )
        )

        # check create two unit node for one panel
        with pytest.raises(GrafanaError):
            grafana_service.link_unit_node_to_panel(
                LinkUnitNodeToPanel(
                    unit_node_uuid=input_unit_node[0].uuid,
                    dashboard_panels_uuid=panel.uuid,
                    is_forced_to_json=True if target_type == DashboardPanelTypeEnum.PIE_CHART else False,
                    is_last_data=False,
                )
            )

    count, input_unit_node = unit_node_service.list(
        UnitNodeFilter(unit_uuid=pytest.units[1].uuid, type=[UnitNodeTypeEnum.INPUT])
    )

    # creation for future deletion
    grafana_service.link_unit_node_to_panel(
        LinkUnitNodeToPanel(
            unit_node_uuid=input_unit_node[0].uuid,
            dashboard_panels_uuid=pytest.delete_panel[0].uuid,
            is_forced_to_json=False,
            is_last_data=False,
        )
    )


@pytest.mark.run(order=5)
async def test_sync_dashboard(database, cc) -> None:

    current_user = pytest.users[0]
    grafana_service = get_grafana_service(database, cc, pytest.user_tokens_dict[current_user.uuid])

    # check sync
    dashboard = await grafana_service.sync_dashboard(pytest.dashboards[0].uuid)
    assert dashboard.sync_status == DashboardStatus.SUCCESS


@pytest.mark.run(order=6)
def test_get_dashboard(database, cc) -> None:

    current_user = pytest.users[0]
    grafana_service = get_grafana_service(database, cc, pytest.user_tokens_dict[current_user.uuid])

    # check get 0 dashboard
    grafana_service.get_dashboard(pytest.dashboards[0].uuid)


@pytest.mark.run(order=7)
def test_list_dashboards(database, cc) -> None:

    current_user = pytest.users[0]
    grafana_service = get_grafana_service(database, cc, pytest.user_tokens_dict[current_user.uuid])

    # check get all dashboards
    count, dashboards = grafana_service.list_dashboards(DashboardFilter(search_string='test', offset=0, limit=10))

    assert count >= 2


@pytest.mark.run(order=8)
def test_get_dashboard_panels(database, cc) -> None:

    current_user = pytest.users[0]
    grafana_service = get_grafana_service(database, cc, pytest.user_tokens_dict[current_user.uuid])

    # check get data for 0 dashboard
    panels = grafana_service.get_dashboard_panels(pytest.dashboards[0].uuid)

    assert panels.count >= 4


@pytest.mark.run(order=9)
def test_get_dashboard_panels(database, cc) -> None:

    current_user = pytest.users[0]
    grafana_service = get_grafana_service(database, cc, pytest.user_tokens_dict[current_user.uuid])

    # check get data for 0 dashboard
    panels = grafana_service.get_dashboard_panels(pytest.dashboards[0].uuid)

    assert panels.count >= 4


@pytest.mark.run(order=10)
def test_delete_link(database, cc) -> None:

    current_user = pytest.users[0]
    unit_node_service = get_unit_node_service(database, cc, pytest.user_tokens_dict[current_user.uuid])
    grafana_service = get_grafana_service(database, cc, pytest.user_tokens_dict[current_user.uuid])

    count, input_unit_node = unit_node_service.list(
        UnitNodeFilter(unit_uuid=pytest.units[1].uuid, type=[UnitNodeTypeEnum.INPUT])
    )

    grafana_service.delete_link(
        unit_node_uuid=input_unit_node[0].uuid, dashboard_panel_uuid=pytest.delete_panel[0].uuid
    )


@pytest.mark.run(order=11)
def test_delete_panel(database, cc) -> None:

    current_user = pytest.users[0]
    grafana_service = get_grafana_service(database, cc, pytest.user_tokens_dict[current_user.uuid])

    grafana_service.delete_panel(uuid=pytest.delete_panel[0].uuid)


@pytest.mark.run(order=12)
def test_delete_panel(database, cc) -> None:

    current_user = pytest.users[0]
    grafana_service = get_grafana_service(database, cc, pytest.user_tokens_dict[current_user.uuid])

    grafana_service.delete_dashboard(uuid=pytest.dashboards[1].uuid)
