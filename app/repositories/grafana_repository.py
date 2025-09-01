import base64
import copy
import json
from typing import List

import httpx

from app import settings
from app.domain.dashboard_model import Dashboard
from app.domain.dashboard_panel_model import DashboardPanel


class GrafanaRepository:
    admin_token: str = base64.b64encode(
        f'{settings.gf_admin_user}:{settings.gf_admin_password}'.encode('utf-8')
    ).decode('utf-8')

    headers: dict = {"Authorization": 'Basic ' + admin_token, "Content-Type": "application/json"}

    base_grafana_url: str = f"{settings.backend_link}/grafana"

    def generate_dashboard(self, dashboard: Dashboard, panels: List[DashboardPanel]) -> dict:
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
                                "format": "table",
                                "json": {"type": "json", "parser": "JSONata", "rootSelector": "$"},
                                "url": "",
                                "url_options": {
                                    "method": "GET",
                                    "data": "",
                                    "headers": [{"key": "header-key", "value": "header-value"}],
                                    "params": [{"key": "format", "value": "table"}],
                                },
                            }
                        ],
                        "fieldConfig": {"defaults": {}, "overrides": []},
                    }
                    for panel in panels
                ],
            },
            "overwrite": True,
        }

    def sync_dashboard(self, current_org: int, dashboard: Dashboard, panels: List[DashboardPanel]):
        headers_deepcopy = copy.deepcopy(self.headers)
        headers_deepcopy['X-Grafana-Org-Id'] = str(current_org)

        response = httpx.post(
            f'{self.base_grafana_url}/api/dashboards/db',
            headers=headers_deepcopy,
            data=self.generate_dashboard(dashboard, panels),
        )
