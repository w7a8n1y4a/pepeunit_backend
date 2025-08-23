import random
import time
import uuid
from datetime import datetime, timedelta
from typing import Optional

import requests  # добавляем для вызова Grafana API
from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import RedirectResponse
from starlette.responses import JSONResponse

from app import settings
from app.configs.db import get_hand_session
from app.configs.rest import get_user_service
from app.domain.user_model import User
from app.dto.enum import CookieName, GrafanaUserRole
from app.utils.utils import generate_random_string

router = APIRouter()
auth_codes = {}
access_tokens = {}

GRAFANA_URL = "https://localunit.pepeunit.com/grafana"
GRAFANA_ADMIN_TOKEN = "Basic YWRtaW46cGFzc3dvcmQ="


def create_org_if_not_exists(user: User):
    headers = {"Authorization": GRAFANA_ADMIN_TOKEN, "Content-Type": "application/json"}

    # Получаем список организаций
    resp = requests.get(f"{GRAFANA_URL}/api/orgs", headers=headers)
    resp.raise_for_status()
    orgs = resp.json()

    existing = next((o for o in orgs if o["name"] == str(user.grafana_org_name)), None)
    if not existing:
        # Создаём новую организацию
        resp = requests.post(f"{GRAFANA_URL}/api/orgs", headers=headers, json={"name": str(user.grafana_org_name)})
        resp.raise_for_status()
        org_id = resp.json().get("orgId")
    else:
        org_id = existing["id"]

    resp = requests.post(
        f"{GRAFANA_URL}/api/admin/users",
        headers=headers,
        json={"name": user.login, "email": user.login, "login": user.login, "password": generate_random_string(16)},
    )
    print(resp.json())

    if resp.status_code not in (200, 412):
        resp.raise_for_status()

    # Добавляем пользователя в организацию
    resp = requests.post(
        f"{GRAFANA_URL}/api/orgs/{org_id}/users",
        headers=headers,
        json={"loginOrEmail": user.login, "role": GrafanaUserRole.EDITOR.value},
    )
    print(resp.json())

    if resp.status_code not in (200, 409):
        resp.raise_for_status()

    return org_id


@router.get("/oidc/authorize")
def authorize(request: Request, client_id: str, redirect_uri: str, scope: str, state: str, nonce: Optional[str] = None):
    session_cookie = request.cookies
    with get_hand_session() as db:
        user_service = get_user_service(db=db, jwt_token=session_cookie.get(CookieName.PEPEUNIT_GRAFANA.value, None))

        current_user = user_service.get(user_service.access_service.current_agent.uuid)

    create_org_if_not_exists(current_user)

    code = str(uuid.uuid4())
    auth_codes[code] = {
        "client_id": client_id,
        "scope": scope,
        "nonce": nonce,
        "issued_at": time.time(),
        "user": {
            "sub": str(current_user.uuid),
            "name": current_user.login,
            "email": current_user.login,
            "role": GrafanaUserRole.EDITOR.value,
            "organization": str(current_user.grafana_org_name),
        },
    }

    return RedirectResponse(url=f"{redirect_uri}?code={code}&state={state}")


import jwt

SECRET_KEY = "dummy"  # лучше вынести в settings
ALGORITHM = "HS256"


def generate_id_token(user):
    now = int(time.time())
    payload = {
        "sub": str(user["sub"]),
        "name": user["name"],
        "email": user["email"],
        "role": user["role"],
        "organization": user["organization"],
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


@router.post("/oidc/token")
def token(code: str = Form(...)):
    print('two', code)
    if code not in auth_codes.keys():
        return JSONResponse(status_code=400, content={"error": "invalid_grant"})

    id_token = generate_id_token(auth_codes[code]["user"])
    access_token = generate_id_token(auth_codes[code]["user"])

    auth_codes.pop(code)
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

    print(auth.split(' ')[1])

    return jwt.decode(auth.split(' ')[1], SECRET_KEY, algorithms=[ALGORITHM])


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
