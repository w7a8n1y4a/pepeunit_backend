import base64
import copy
import json
import logging
import string
import time

import httpx
from fastapi import Depends

from app import settings
from app.configs.errors import GrafanaError
from app.domain.dashboard_model import Dashboard
from app.domain.panels_unit_nodes_model import PanelsUnitNodes
from app.domain.user_model import User
from app.dto.agent.abc import AgentGrafanaUnitNode
from app.dto.clickhouse.aggregation import Aggregation
from app.dto.clickhouse.last_value import LastValue
from app.dto.clickhouse.n_records import NRecords
from app.dto.clickhouse.time_window import TimeWindow
from app.dto.enum import (
    DatasourceFormat,
    GrafanaUserRole,
    ProcessingPolicyType,
    TypeInputValue,
)
from app.repositories.data_pipe_repository import DataPipeRepository
from app.schemas.pydantic.grafana import (
    DashboardPanelRead,
    DatasourceTimeSeriesData,
    UnitNodeForPanel,
)
from app.schemas.pydantic.unit_node import DataPipeFilter
from app.utils.utils import generate_random_string
from app.validators.data_pipe import DataPipeConfig, is_valid_data_pipe_config


class GrafanaRepository:
    def __init__(
        self,
        data_pipe_repository: DataPipeRepository = Depends(),
    ) -> None:
        self.data_pipe_repository = data_pipe_repository

    admin_token: str = base64.b64encode(
        f"{settings.pu_grafana_admin_user}:{settings.pu_grafana_admin_password}".encode()
    ).decode("utf-8")
    headers: dict = {
        "Authorization": "Basic " + admin_token,
        "Content-Type": "application/json",
    }
    base_grafana_url: str = f"{settings.pu_link}/grafana"

    @classmethod
    def configure_admin_dashboard_permissions(cls) -> None:
        folder_title = "Admin"
        headers = copy.deepcopy(cls.headers)
        headers.setdefault("X-Grafana-Org-Id", "1")

        while True:
            try:
                response = httpx.get(
                    f"{cls.base_grafana_url}/api/search",
                    headers=headers,
                    params={"query": folder_title, "type": "dash-folder"},
                    timeout=10.0,
                )
                response.raise_for_status()

                folders = [
                    item
                    for item in response.json()
                    if item.get("type") == "dash-folder"
                    and item.get("title") == folder_title
                ]

                if not folders or not folders[0].get("uid"):
                    msg = "Not found admin folder for set Permissions"
                    raise GrafanaError(msg)

                url = f"{cls.base_grafana_url}/api/folders/{folders[0]['uid']}/permissions"

                response = httpx.get(url, headers=headers, timeout=10.0)
                response.raise_for_status()

                admin_permissions = [
                    permission
                    for permission in response.json()
                    if permission.get("role") == "Admin"
                    or permission.get("permission") == 4
                ]

                if not admin_permissions:
                    admin_permissions = [{"role": "Admin", "permission": 4}]

                response = httpx.post(
                    url,
                    headers=headers,
                    json={"items": admin_permissions},
                    timeout=10.0,
                )
                response.raise_for_status()
                break
            except Exception as exc:
                logging.error(exc)
                time.sleep(10)

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

    async def generate_dashboard(
        self, dashboard: Dashboard, panels: list[DashboardPanelRead]
    ) -> dict:
        if len(panels) == 0:
            msg = "Dashboard does not have Panels"
            raise GrafanaError(msg)

        panels_list = []
        for panel in panels:
            targets_list = []
            for ref_id, unit_node in self.enumerate_refid(
                panel.unit_nodes_for_panel
            ):
                if not unit_node.unit_node.is_data_pipe_active:
                    msg = f"{unit_node.unit_with_unit_node_name} has no active DataPipe"
                    raise GrafanaError(msg)

                data_pipe_dict = json.loads(unit_node.unit_node.data_pipe_yml)
                data_pipe_entity = is_valid_data_pipe_config(
                    data_pipe_dict, is_business_validator=True
                )

                if (
                    isinstance(data_pipe_entity, list)
                    or unit_node.unit_node.data_pipe_yml is None
                ):
                    msg = f"{unit_node.unit_with_unit_node_name} has no valid yml DataPipe"
                    raise GrafanaError(msg)

                columns, root_selector = self.get_columns(
                    unit_node, data_pipe_entity
                )

                target_dict = {
                    "datasource": "InfinityAPI",
                    "refId": ref_id,
                    "root_selector": root_selector,
                    "format": DatasourceFormat.TIME_SERIES,
                    "parser": "backend",
                    "json": {
                        "type": "json",
                        "parser": "JSONata",
                        "rootSelector": "$",
                    },
                    "url": "",
                    "url_options": {
                        "method": "GET",
                        "data": "",
                        "headers": [
                            {
                                "key": "x-auth-token",
                                "value": AgentGrafanaUnitNode(
                                    uuid=unit_node.unit_node.uuid,
                                    panel_uuid=panel.uuid,
                                    name="grafana",
                                ).generate_agent_token(),
                            }
                        ],
                        "params": [
                            {"key": key, "value": value}
                            for key, value in (
                                await self.get_params(data_pipe_entity)
                            ).items()
                        ],
                    },
                    "columns": columns,
                }
                targets_list.append(target_dict)

            panel_dict = {
                "type": panel.type,
                "title": panel.title,
                "gridPos": {"x": 0, "y": 0, "w": 24, "h": 8},
                "options": {},
                "fieldConfig": {
                    "defaults": {
                        "custom": {
                            "invertPalette": True,
                        },
                    },
                    "overrides": [],
                },
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
                "time": {"from": "now-30d", "to": "now"},
            },
            "overwrite": True,
        }

    def sync_dashboard(self, current_org: str, dashboard_dict: dict) -> dict:
        headers_deepcopy = copy.deepcopy(self.headers)
        headers_deepcopy["X-Grafana-Org-Id"] = current_org

        response = httpx.post(
            f"{self.base_grafana_url}/api/dashboards/db",
            headers=headers_deepcopy,
            data=json.dumps(dashboard_dict),
        )

        response.raise_for_status()

        return response.json()

    @staticmethod
    async def get_params(data_pipe_entity: DataPipeConfig) -> dict:
        params = {
            "format": DatasourceFormat.TIME_SERIES,
            "order_by_create_date": "asc",
        }

        # BUG: limit можно прописывать только руками. При генерации, он ломает и пишет ошибку Unknown Query Type у панелей

        """
        if unit_node.is_last_data or data_pipe_entity.processing_policy.policy_type == ProcessingPolicyType.LAST_VALUE:
            params['limit'] = 1

        if data_pipe_entity.processing_policy.policy_type == ProcessingPolicyType.N_RECORDS:
            params['limit'] = data_pipe_entity.processing_policy.n_records_count
        """

        if (
            data_pipe_entity.processing_policy.policy_type
            == ProcessingPolicyType.TIME_WINDOW
        ):
            params["relative_time"] = (
                str(data_pipe_entity.processing_policy.time_window_size) + "s"
            )

        if (
            data_pipe_entity.processing_policy.policy_type
            == ProcessingPolicyType.AGGREGATION
        ):
            params["relative_time"] = "30d"

        return params

    def get_columns(
        self,
        unit_node_panel: UnitNodeForPanel,
        data_pipe_entity: DataPipeConfig,
    ) -> tuple[list[dict], str]:
        data = self.get_datasource_data(
            DataPipeFilter(
                uuid=unit_node_panel.unit_node.uuid,
                type=data_pipe_entity.processing_policy.policy_type,
                limit=1,
            ),
            data_pipe_entity,
            unit_node_panel,
        )

        columns = [{"selector": "time", "text": "", "type": "timestamp_epoch"}]
        root_selector = ""

        if len(data) == 0:
            return columns, ""
        if isinstance(data[0].value, str):
            columns.append({"selector": "value", "text": "", "type": "string"})
        elif isinstance(data[0].value, float | int):
            columns.append({"selector": "value", "text": "", "type": "number"})
        elif isinstance(data[0].value, dict):
            root_selector = "value"
            for key, value in data[0].value.items():
                if isinstance(value, float | int):
                    columns.append(
                        {"selector": key, "text": "", "type": "number"}
                    )
                if isinstance(value, str):
                    columns.append(
                        {"selector": key, "text": "", "type": "string"}
                    )

        return columns, root_selector

    def get_datasource_data(
        self,
        filters: DataPipeFilter,
        data_pipe_entity: DataPipeConfig,
        unit_node_panel: PanelsUnitNodes | UnitNodeForPanel,
    ) -> list[DatasourceTimeSeriesData]:
        count, data = self.data_pipe_repository.list(filters=filters)

        return [
            DatasourceTimeSeriesData(
                time=self.get_time_datasource_value(item),
                value=self.get_typed_datasource_value(
                    item.state, data_pipe_entity, unit_node_panel
                ),
            )
            for item in data
        ]

    @staticmethod
    def get_typed_datasource_value(
        value: str,
        data_pipe_entity: DataPipeConfig,
        unit_node_panel: PanelsUnitNodes,
    ) -> str | float | dict:
        if unit_node_panel.is_forced_to_json:
            return json.loads(value)
        if data_pipe_entity.filters.type_input_value == TypeInputValue.NUMBER:
            return float(value)
        if data_pipe_entity.filters.type_input_value == TypeInputValue.TEXT:
            return value
        msg = "Processing this value not supported"
        raise GrafanaError(msg)

    @staticmethod
    def get_time_datasource_value(
        data: NRecords | TimeWindow | Aggregation | LastValue,
    ) -> int:
        value = None
        if isinstance(data, NRecords):
            value = data.create_datetime
        if isinstance(data, TimeWindow):
            value = data.create_datetime
        if isinstance(data, Aggregation):
            value = data.end_window_datetime
        if isinstance(data, LastValue):
            value = data.last_update_datetime

        if value:
            return int(value.timestamp() * 1000)
        msg = "Data type not supported"
        raise GrafanaError(msg)

    def create_org_if_not_exists(self, user: User):
        resp = httpx.get(
            f"{settings.pu_link}/grafana/api/orgs", headers=self.headers
        )
        resp.raise_for_status()

        orgs = [
            org
            for org in resp.json()
            if org["name"] == str(user.grafana_org_name)
        ]
        target_org = orgs[0] if orgs else None

        if not target_org:
            resp = httpx.post(
                f"{settings.pu_link}/grafana/api/orgs",
                headers=self.headers,
                json={"name": str(user.grafana_org_name)},
            )
            resp.raise_for_status()
            org_id = resp.json().get("orgId")
        else:
            org_id = target_org["id"]

        resp = httpx.post(
            f"{settings.pu_link}/grafana/api/admin/users",
            headers=self.headers,
            json={
                "name": user.login,
                "email": user.login,
                "login": user.login,
                "password": generate_random_string(16),
            },
        )

        if resp.status_code not in (200, 412):
            resp.raise_for_status()

        resp = httpx.post(
            f"{settings.pu_link}/grafana/api/orgs/{org_id}/users",
            headers=self.headers,
            json={
                "loginOrEmail": user.login,
                "role": GrafanaUserRole.EDITOR.value,
            },
        )

        if resp.status_code not in (200, 409):
            resp.raise_for_status()

        datasource_payload = {
            "name": "InfinityAPI",
            "type": "yesoreyeram-infinity-datasource",
            "access": "proxy",
            "url": f"{settings.pu_link_prefix_and_v1}/grafana/datasource/",
            "jsonData": {
                "auth_method": None,
                "customHealthCheckEnabled": True,
                "customHealthCheckUrl": settings.pu_link_prefix,
            },
        }

        headers_deepcopy = copy.deepcopy(self.headers)
        headers_deepcopy["X-Grafana-Org-Id"] = str(org_id)

        resp = httpx.post(
            f"{settings.pu_link}/grafana/api/datasources",
            headers=headers_deepcopy,
            json=datasource_payload,
        )

        if resp.status_code not in (200, 409):
            resp.raise_for_status()

        return org_id
