import json
import uuid

import requests

# Конфигурация
GRAFANA_URL = "https://localunit.pepeunit.com/grafana"  # URL Grafana
API_KEY = "YWRtaW46cGFzc3dvcmQ="  # Токен авторизации

headers = {"Authorization": f"Basic {API_KEY}", "Content-Type": "application/json"}
headers['X-Grafana-Org-Id'] = str(2)

test_uuid = str('5d0e2300-d7a4-4d3d-9c70-5dcc9910a8ae')

print(test_uuid)
dashboard = {
    "dashboard": {
        "id": None,
        "uid": test_uuid,
        "title": f"Tasks {test_uuid[:10]}",
        "tags": ["tasks", "infinity"],
        "timezone": "browser",
        "schemaVersion": 30,
        "version": 2,
        "refresh": "5s",
        "panels": [
            {
                "type": "table",
                "title": "Список задач",
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
            },
            {
                "type": "timeseries",
                "title": "Timeseries",
                "gridPos": {"x": 0, "y": 0, "w": 24, "h": 8},
                "options": {
                    "showHeader": True,
                },
                "targets": [
                    {
                        "datasource": "yesoreyeram-infinity-datasource",
                        "refId": "A",
                        "format": "timeseries",
                        "json": {"type": "json", "parser": "JSONata", "rootSelector": "$"},
                        "url": "",
                        "url_options": {
                            "method": "GET",
                            "data": "",
                            "headers": [{"key": "header-key", "value": "header-value"}],
                            "params": [{"key": "format", "value": "timeseries"}],
                        },
                    }
                ],
                "fieldConfig": {"defaults": {}, "overrides": []},
            },
        ],
    },
    "overwrite": True,
}

response = requests.post(f"{GRAFANA_URL}/api/dashboards/db", headers=headers, data=json.dumps(dashboard))

print(response.status_code)
print(response.text)
