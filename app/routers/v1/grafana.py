import base64
import json
import random
import time
import uuid
from datetime import datetime, timedelta
from typing import Optional

import httpx
from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import RedirectResponse
from starlette.responses import JSONResponse

from app import settings
from app.configs.db import get_hand_session
from app.configs.redis import get_redis_session
from app.configs.rest import get_user_service
from app.domain.user_model import User
from app.dto.enum import CookieName, GrafanaUserRole
from app.utils.utils import generate_random_string

router = APIRouter()


def create_org_if_not_exists(user: User):
    admin_token = base64.b64encode(f'{settings.gf_admin_user}:{settings.gf_admin_password}'.encode('utf-8')).decode(
        'utf-8'
    )
    headers = {"Authorization": 'Basic ' + admin_token, "Content-Type": "application/json"}

    resp = httpx.get(f"{settings.backend_link}/grafana/api/orgs", headers=headers)
    resp.raise_for_status()
    orgs = resp.json()

    existing = next((o for o in orgs if o["name"] == str(user.grafana_org_name)), None)
    if not existing:
        resp = httpx.post(
            f"{settings.backend_link}/grafana/api/orgs", headers=headers, json={"name": str(user.grafana_org_name)}
        )
        resp.raise_for_status()
        org_id = resp.json().get("orgId")
    else:
        org_id = existing["id"]

    resp = httpx.post(
        f"{settings.backend_link}/grafana/api/admin/users",
        headers=headers,
        json={"name": user.login, "email": user.login, "login": user.login, "password": generate_random_string(16)},
    )

    if resp.status_code not in (200, 412):
        resp.raise_for_status()

    resp = httpx.post(
        f"{settings.backend_link}/grafana/api/orgs/{org_id}/users",
        headers=headers,
        json={"loginOrEmail": user.login, "role": GrafanaUserRole.EDITOR.value},
    )

    if resp.status_code not in (200, 409):
        resp.raise_for_status()

    datasource_payload = {
        "name": "InfinityAPI",
        "type": "yesoreyeram-infinity-datasource",
        "access": "proxy",
        "url": f"{settings.backend_link_prefix_and_v1}/unit_nodes/datasource/",
        "jsonData": {
            "auth_method": None,
            "customHealthCheckEnabled": True,
            "customHealthCheckUrl": settings.backend_link_prefix,
        },
    }

    headers['X-Grafana-Org-Id'] = str(org_id)
    resp = httpx.post(
        f"{settings.backend_link}/grafana/api/datasources",
        headers=headers,
        json=datasource_payload,
    )

    if resp.status_code not in (200, 409):
        resp.raise_for_status()

    return org_id


@router.get("/oidc/authorize")
async def authorize(
    request: Request, client_id: str, redirect_uri: str, scope: str, state: str, nonce: Optional[str] = None
):
    session_cookie = request.cookies
    with get_hand_session() as db:
        user_service = get_user_service(db=db, jwt_token=session_cookie.get(CookieName.PEPEUNIT_GRAFANA.value, None))

        current_user = user_service.get(user_service.access_service.current_agent.uuid)

    create_org_if_not_exists(current_user)

    redis = await anext(get_redis_session())

    code = str(uuid.uuid4())
    await redis.set(
        f'grafana:{code}',
        json.dumps(
            {
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
        ),
        ex=60,
    )

    return RedirectResponse(url=f"{redirect_uri}?code={code}&state={state}")


@router.post("/oidc/token")
async def token(
    code: str = Form(...),
):
    redis = await anext(get_redis_session())

    auth_data = await redis.get(f'grafana:{code}')
    if not auth_data:
        return JSONResponse(status_code=400, content={"error": "invalid_grant"})

    return {
        "access_token": code,
        "token_type": "Bearer",
        "expires_in": 3600,
    }


@router.get("/oidc/userinfo")
async def userinfo(request: Request):
    auth = request.headers.get("Authorization")

    if not auth or not auth.startswith("Bearer "):
        return JSONResponse(status_code=401, content={"error": "invalid_token"})

    code = auth.split(" ")[1]

    redis = await anext(get_redis_session())

    auth_data = await redis.get(f'grafana:{code}')
    if not auth_data:
        return JSONResponse(status_code=400, content={"error": "invalid_grant"})

    await redis.delete(f'grafana:{code}')

    return json.loads(auth_data)['user']
