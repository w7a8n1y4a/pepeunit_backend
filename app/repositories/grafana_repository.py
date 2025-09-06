import base64
import copy
import json
import string

import httpx

from app import settings
from app.domain.dashboard_model import Dashboard
from app.dto.agent.abc import AgentGrafanaUnitNode
from app.dto.enum import DatasourceFormat, ProcessingPolicyType
from app.schemas.pydantic.grafana import DashboardPanelsRead, UnitNodeForPanel
from app.validators.data_pipe import is_valid_data_pipe_config


class GrafanaRepository:
    admin_token: str = base64.b64encode(
        f'{settings.gf_admin_user}:{settings.gf_admin_password}'.encode('utf-8')
    ).decode('utf-8')
    headers: dict = {"Authorization": 'Basic ' + admin_token, "Content-Type": "application/json"}
    base_grafana_url: str = f"{settings.backend_link}/grafana"

    @staticmethod
    def enumerate_refid(iterable, start=0):
        def refid_generator():
            letters = string.ascii_uppercase
            length = 1
            while True:
                for i in range(len(letters) ** length):
                    result = ""
                    n = i
                    for _ in range(length):
                        result = letters[n % len(letters)] + result
                        n //= len(letters)
                    yield result
                length += 1

        gen = refid_generator()
        for _ in range(start):
            next(gen)
        for item in iterable:
            yield next(gen), item

    async def generate_dashboard(self, dashboard: Dashboard, panels: list[DashboardPanelsRead]) -> dict:

        panels_list = []
        for panel in panels:

            targets_list = []
            for ref_id, unit_node in self.enumerate_refid(panel.unit_nodes_for_panel):

                target_dict = {
                    "datasource": "yesoreyeram-infinity-datasource",
                    "refId": ref_id,
                    "format": await self.get_targets_format_by_data_pipe(unit_node),
                    "json": {"type": "json", "parser": "JSONata", "rootSelector": "$"},
                    "url": "",
                    "url_options": {
                        "method": "GET",
                        "data": "",
                        "headers": [
                            {
                                "key": "x-auth-token",
                                "value": AgentGrafanaUnitNode(
                                    uuid=unit_node.unit_node.uuid, name='grafana'
                                ).generate_agent_token(),
                            }
                        ],
                        "params": [
                            {"key": key, "value": value} for key, value in (await self.get_params(unit_node)).items()
                        ],
                    },
                    "columns": [
                        {"selector": "time", "text": "", "type": "timestamp_epoch"},
                        {"selector": "value", "text": "", "type": "number"},
                    ],
                }
                targets_list.append(target_dict)

            panel_dict = {
                "type": panel.type,
                "title": panel.title,
                "gridPos": {"x": 0, "y": 0, "w": 24, "h": 8},
                "options": {
                    "from": "0",
                    "legendGradientQuality": "high",
                    "showCellBorder": False,
                    "showHeader": True,
                    "showLegend": True,
                    "showTooltip": True,
                    "showValueIndicator": False,
                    "timeFieldName": "Time",
                    "to": "0",
                    "valueFieldName": "Value",
                },
                "fieldConfig": {"defaults": {}, "overrides": []},
                "targets": targets_list,
            }

            panels_list.append(panel_dict)

        return {
            "dashboard": {
                "id": None,
                "uid": str(dashboard.grafana_uuid),
                "title": dashboard.name,
                "tags": [dashboard.name],
                "timezone": "browser",
                "schemaVersion": 30,
                "refresh": "1m",
                "panels": panels_list,
                "time": {"from": "now-60d", "to": "now"},
            },
            "overwrite": True,
        }

    def sync_dashboard(self, current_org: str, dashboard_dict: dict) -> dict:
        headers_deepcopy = copy.deepcopy(self.headers)
        headers_deepcopy['X-Grafana-Org-Id'] = current_org

        response = httpx.post(
            f'{self.base_grafana_url}/api/dashboards/db',
            headers=headers_deepcopy,
            data=json.dumps(dashboard_dict),
        )

        response.raise_for_status()

        return response.json()

    async def get_params(self, unit_node: UnitNodeForPanel) -> dict:
        data_pipe_dict = json.loads(unit_node.unit_node.data_pipe_yml)
        data_pipe_entity = is_valid_data_pipe_config(data_pipe_dict, is_business_validator=True)

        params = {
            "format": await self.get_targets_format_by_data_pipe(unit_node),
            "order_by_create_date": "asc",
        }

        if data_pipe_entity.processing_policy.policy_type == ProcessingPolicyType.TIME_WINDOW:
            params['relative_time'] = str(data_pipe_entity.processing_policy.time_window_size) + 's'

        if data_pipe_entity.processing_policy.policy_type == ProcessingPolicyType.N_RECORDS:
            params['limit'] = data_pipe_entity.processing_policy.n_records_count

        if data_pipe_entity.processing_policy.policy_type == ProcessingPolicyType.AGGREGATION:
            params['relative_time'] = '60d'

        if unit_node.is_last_data or data_pipe_entity.processing_policy.policy_type == ProcessingPolicyType.LAST_VALUE:
            params['limit'] = 1

        return params

    @staticmethod
    async def get_targets_format_by_data_pipe(unit_node: UnitNodeForPanel) -> DatasourceFormat:
        data_pipe_dict = json.loads(unit_node.unit_node.data_pipe_yml)
        data_pipe_entity = is_valid_data_pipe_config(data_pipe_dict, is_business_validator=True)

        if unit_node.is_last_data or data_pipe_entity.processing_policy.policy_type == ProcessingPolicyType.LAST_VALUE:
            return DatasourceFormat.TABLE
        else:
            return DatasourceFormat.TIME_SERIES
