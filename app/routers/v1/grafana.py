import random
import time
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import RedirectResponse
from starlette.responses import JSONResponse

from app import settings
from app.configs.errors import NoAccessError
from app.configs.rest import get_user_service
from app.services.user_service import UserService

router = APIRouter()
auth_codes = {}
access_tokens = {}

"""
[server]
root_url = http://localhost:3000/pepeunit/grafana/
serve_from_sub_path = true

[organizations]
allow_organization_creation = true


[auth]
disable_login_form = true  # Чтобы не мешала форма логина Grafana

[auth.generic_oauth]
enabled = true
name = Pepeunit
allow_sign_up = true
client_id = grafana-client
client_secret = dummy
scopes = openid profile email
auth_url = http://192.168.0.22:8555/pepeunit/api/v1/grafana/oidc/authorize
token_url = http://192.168.0.22:8555/pepeunit/api/v1/grafana/oidc/token
api_url = http://192.168.0.22:8555/pepeunit/api/v1/grafana/oidc/userinfo
email_attribute_path = email
login_attribute_path = name
role_attribute_path = role
role_attribute_strict = true


"""


@router.get("/oidc/authorize")
def authorize(
    response_type: str, client_id: str, redirect_uri: str, scope: str, state: str, nonce: Optional[str] = None
):
    """
    Простая авторизация: возвращает редирект с "кодом" обратно в Grafana.
    """
    code = str(uuid.uuid4())
    auth_codes[code] = {
        "client_id": client_id,
        "scope": scope,
        "nonce": nonce,
        "issued_at": time.time(),
        "user": {"sub": "1234", "name": "Grafana User", "email": "grafana@example.com", "role": "Admin"},
    }
    print()

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
    print(auth_codes)
    print(access_tokens)
    if code not in auth_codes.keys():
        return JSONResponse(status_code=400, content={"error": "invalid_grant"})

    # Выдать "токен"
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
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        return JSONResponse(status_code=401, content={"error": "invalid_token"})

    token = auth.split(" ")[1]
    if token not in access_tokens:
        return JSONResponse(status_code=401, content={"error": "invalid_token"})

    user = access_tokens[token]["user"]
    return {"sub": user["sub"], "name": user["name"], "email": user["email"], "role": user["role"]}


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
