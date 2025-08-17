import json
import uuid

import requests

# Конфигурация
GRAFANA_URL = "http://localhost:3000/pepeunit/grafana"  # URL Grafana
API_KEY = ""  # Токен авторизации

headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

# Имя вашего источника данных Infinity в Grafana
DATASOURCE_NAME = "Infinity"

dashboard = {
    "dashboard": {
        "id": None,
        "uid": None,
        "title": f"Tasks {str(uuid.uuid4())[:10]}",
        "tags": ["tasks", "infinity"],
        "timezone": "browser",
        "schemaVersion": 30,
        "version": 0,
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
