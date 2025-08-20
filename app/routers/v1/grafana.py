import random
import time
import uuid
from datetime import datetime, timedelta
from typing import Optional

import requests  # добавляем для вызова Grafana API
from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import RedirectResponse
from starlette.responses import JSONResponse

router = APIRouter()
auth_codes = {}
access_tokens = {}

# === настройки для Grafana API ===
GRAFANA_URL = "http://localhost:3000"  # адрес твоей Grafana
GRAFANA_ADMIN_TOKEN = "Basic YWRtaW46cGFzc3dvcmQ="


def create_org_if_not_exists(org_name: str, user_email: str, role: str = "Admin"):
    headers = {"Authorization": GRAFANA_ADMIN_TOKEN, "Content-Type": "application/json"}

    # Получаем список организаций
    resp = requests.get(f"{GRAFANA_URL}/api/orgs", headers=headers)
    resp.raise_for_status()
    orgs = resp.json()

    existing = next((o for o in orgs if o["name"] == org_name), None)
    if not existing:
        # Создаём новую организацию
        resp = requests.post(f"{GRAFANA_URL}/api/orgs", headers=headers, json={"name": org_name})
        resp.raise_for_status()
        org_id = resp.json().get("orgId")
    else:
        org_id = existing["id"]

    # Создаём пользователя, если его нет
    resp = requests.post(
        f"{GRAFANA_URL}/api/admin/users",
        headers=headers,
        json={"name": user_email.split("@")[0], "email": user_email, "login": user_email, "password": "TempPass123!"},
    )
    if resp.status_code not in (200, 409):  # 409 = уже существует
        resp.raise_for_status()

    # Добавляем пользователя в организацию
    resp = requests.post(
        f"{GRAFANA_URL}/api/orgs/{org_id}/users",
        headers=headers,
        json={"loginOrEmail": user_email, "role": role},
    )
    print(resp.json())

    if resp.status_code not in (200, 409):
        resp.raise_for_status()

    return org_id


@router.get("/oidc/authorize")
def authorize(
    response_type: str, client_id: str, redirect_uri: str, scope: str, state: str, nonce: Optional[str] = None
):
    print(redirect_uri)
    print('one', client_id)
    """
    Простая авторизация: возвращает редирект с "кодом" обратно в Grafana.
    """
    code = str(uuid.uuid4())

    # создаём уникального юзера
    user_id = str(uuid.uuid4())
    user_email = f"user_{user_id[:8]}@example.com"
    user_name = f"GrafanaUser-{user_id[:8]}"
    org_name = f"org-{user_id[:8]}"

    # Создаём организацию в Grafana (если нет)
    create_org_if_not_exists(org_name, user_email, role="Admin")

    auth_codes[code] = {
        "client_id": client_id,
        "scope": scope,
        "nonce": nonce,
        "issued_at": time.time(),
        "user": {
            "sub": user_id,
            "name": user_name,
            "email": user_email,
            "role": "Admin",  # чтобы гарантировать создание организации
            "organization": org_name,
        },
    }

    redirect_url = f"{redirect_uri}?code={code}&state={state}"
    return RedirectResponse(url=redirect_url)


@router.post("/oidc/token")
def token(
    grant_type: str = Form(...),
    code: str = Form(...),
    redirect_uri: str = Form(...),
    client_id: str = Form(...),
    client_secret: str = Form(...),
):
    print('two', code)
    if code not in auth_codes.keys():
        return JSONResponse(status_code=400, content={"error": "invalid_grant"})

    access_token = str(uuid.uuid4())
    id_token = str(uuid.uuid4())
    access_tokens[access_token] = auth_codes.pop(code)

    return {
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": 3600,
        "id_token": id_token,
    }


@router.get("/oidc/userinfo")
def userinfo(request: Request):
    print('three')
    auth = request.headers.get("Authorization")
    print(auth)
    if not auth or not auth.startswith("Bearer "):
        return JSONResponse(status_code=401, content={"error": "invalid_token"})

    token = auth.split(" ")[1]
    if token not in access_tokens:
        return JSONResponse(status_code=401, content={"error": "invalid_token"})

    user = access_tokens[token]["user"]

    return {
        "sub": user["sub"],
        "name": user["name"],
        "email": user["email"],
        "role": user["role"],
        "organization": user["organization"],
    }


@router.get("/api/tasks")
async def get_tasks(format: str = Query("table")):
    if format == "timeseries":
        now = datetime.now()
        now_aligned = now.replace(minute=0, second=0, microsecond=0)
        interval = timedelta(minutes=60)
        days = 90
        points_count = days * 24

        def generate_series():
            timestamps = []
            values = []
            start_time = now_aligned - interval * (points_count - 1)
            for i in range(points_count):
                ts_dt = start_time + interval * i
                ts_ms = int(ts_dt.timestamp() * 1000)
                timestamps.append(ts_ms)
                values.append(random.randint(0, 35))
            return {
                "feeds": [{"time": timestamp, "value": value} for timestamp, value in zip(timestamps, values)],
            }

        return JSONResponse(content=generate_series())

    elif format == "table":
        tasks = [
            {"id": 1, "title": "Сделать отчёт", "status": "в процессе"},
            {"id": 2, "title": "Проверить почту", "status": "завершено"},
            {"id": 3, "title": "Созвон с командой", "status": "в ожидании"},
        ]
        return JSONResponse(content=tasks)
