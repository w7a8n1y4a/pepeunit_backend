import base64
import copy

import httpx

from app import settings
from app.domain.dashboard_model import Dashboard
from app.dto.agent.abc import AgentGrafana
from app.dto.enum import DatasourceFormat, ProcessingPolicyType
from app.schemas.pydantic.grafana import DashboardPanelsRead, UnitNodeForPanel
from app.services.utils import yml_file_to_dict
from app.validators.data_pipe import is_valid_data_pipe_config


class GrafanaRepository:
    admin_token: str = base64.b64encode(
        f'{settings.gf_admin_user}:{settings.gf_admin_password}'.encode('utf-8')
    ).decode('utf-8')

    headers: dict = {"Authorization": 'Basic ' + admin_token, "Content-Type": "application/json"}

    base_grafana_url: str = f"{settings.backend_link}/grafana"

    async def generate_dashboard(self, dashboard: Dashboard, panels: list[DashboardPanelsRead]) -> dict:
        return {
            "dashboard": {
                "id": None,
                "uid": dashboard.grafana_uuid,
                "title": dashboard.name,
                "tags": [dashboard.name],
                "timezone": "browser",
                "schemaVersion": 30,
                "version": 1,
                "refresh": "1m",
                "panels": [
                    {
                        "type": panel.type,
                        "title": panel.title,
                        "gridPos": {"x": 0, "y": 0, "w": 24, "h": 8},
                        "options": {
                            "showHeader": True,
                        },
                        "targets": [
                            {
                                "datasource": "yesoreyeram-infinity-datasource",
                                "refId": "A",
                                "format": await self.get_targets_format_by_data_pipe(unit_node),
                                "json": {"type": "json", "parser": "JSONata", "rootSelector": "$"},
                                "url": "",
                                "url_options": {
                                    "method": "GET",
                                    "data": "",
                                    "headers": [
                                        {
                                            "x-access-token": AgentGrafana(
                                                uuid=unit_node.uuid, name='grafana'
                                            ).generate_agent_token()
                                        }
                                    ],
                                    # TODO должны расчитываться автоматически, хотябы частично
                                    "params": [
                                        {
                                            "format": await self.get_targets_format_by_data_pipe(unit_node),
                                            "order_by_create_date": "asc",
                                            "relative_time": "60d",
                                        }
                                    ],
                                },
                            }
                            for unit_node in panel.unit_nodes_for_panel
                        ],
                        "fieldConfig": {"defaults": {}, "overrides": []},
                    }
                    for panel in panels
                ],
            },
            "overwrite": True,
        }

    def sync_dashboard(self, current_org: str, dashboard_dict: dict) -> dict:
        headers_deepcopy = copy.deepcopy(self.headers)
        headers_deepcopy['X-Grafana-Org-Id'] = current_org

        return httpx.post(
            f'{self.base_grafana_url}/api/dashboards/db',
            headers=headers_deepcopy,
            data=dashboard_dict,
        ).json()

    @staticmethod
    async def get_targets_format_by_data_pipe(unit_node: UnitNodeForPanel) -> DatasourceFormat:
        data_pipe_dict = await yml_file_to_dict(unit_node.unit_node.data_pipe_yml)
        data_pipe_entity = is_valid_data_pipe_config(data_pipe_dict, is_business_validator=True)

        if unit_node.is_last_data or data_pipe_entity.processing_policy.policy_type == ProcessingPolicyType.LAST_VALUE:
            return DatasourceFormat.TABLE
        else:
            return DatasourceFormat.TIME_SERIES
