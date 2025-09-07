import base64
import json
import time
import uuid as uuid_pkg
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from starlette.responses import JSONResponse

from app import settings
from app.configs.db import get_hand_session
from app.configs.redis import get_redis_session
from app.configs.rest import get_grafana_service, get_unit_node_service, get_user_service
from app.domain.user_model import User
from app.dto.enum import CookieName, GrafanaUserRole
from app.schemas.pydantic.grafana import (
    DashboardCreate,
    DashboardFilter,
    DashboardPanelCreate,
    DashboardPanelsRead,
    DashboardPanelsResult,
    DashboardRead,
    DashboardsResult,
    DatasourceFilter,
    LinkUnitNodeToPanel,
    UnitNodeForPanel,
)
from app.services.grafana_service import GrafanaService
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
        "url": f"{settings.backend_link_prefix_and_v1}/grafana/datasource/",
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


@router.post(
    "/create_dashboard",
    response_model=DashboardRead,
    status_code=status.HTTP_201_CREATED,
)
def create_dashboard(data: DashboardCreate, grafana_service: GrafanaService = Depends(get_grafana_service)):
    return grafana_service.create_dashboard(data)


@router.post(
    "/create_dashboard_panel",
    response_model=DashboardPanelsRead,
    status_code=status.HTTP_201_CREATED,
)
def create_dashboard_panel(data: DashboardPanelCreate, grafana_service: GrafanaService = Depends(get_grafana_service)):
    return DashboardPanelsRead(unit_nodes_for_panel=[], **grafana_service.create_dashboard_panel(data).dict())


@router.post(
    "/link_unit_node_to_panel",
    response_model=UnitNodeForPanel,
    status_code=status.HTTP_201_CREATED,
)
def link_unit_node_to_panel(data: LinkUnitNodeToPanel, grafana_service: GrafanaService = Depends(get_grafana_service)):
    return grafana_service.link_unit_node_to_panel(data)


@router.get("/get_dashboard/{uuid}", response_model=DashboardRead)
def get_dashboard(uuid: uuid_pkg.UUID, grafana_service: GrafanaService = Depends(get_grafana_service)):
    return grafana_service.get_dashboard(uuid)


@router.get("/get_dashboards", response_model=DashboardsResult)
def get_dashboards(
    filters: DashboardFilter = Depends(DashboardFilter), grafana_service: GrafanaService = Depends(get_grafana_service)
):
    count, dashboards = grafana_service.list_dashboards(filters)
    return DashboardsResult(count=count, dashboards=[DashboardRead(**dashboard.dict()) for dashboard in dashboards])


@router.get("/get_dashboard_panels/{uuid}", response_model=DashboardPanelsResult)
def get_dashboard_panels(uuid: uuid_pkg.UUID, grafana_service: GrafanaService = Depends(get_grafana_service)):
    return grafana_service.get_dashboard_panels(uuid)


@router.post(
    "/sync_dashboard",
    response_model=DashboardRead,
    status_code=status.HTTP_200_OK,
)
async def sync_dashboard(uuid: uuid_pkg.UUID, grafana_service: GrafanaService = Depends(get_grafana_service)):
    return DashboardRead(**(await grafana_service.sync_dashboard(uuid)).dict())


@router.delete("/delete_dashboard/{uuid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dashboard(uuid: uuid_pkg.UUID, grafana_service: GrafanaService = Depends(get_grafana_service)):
    return grafana_service.delete_dashboard(uuid)


@router.delete("/delete_panel/{uuid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_panel(uuid: uuid_pkg.UUID, grafana_service: GrafanaService = Depends(get_grafana_service)):
    return grafana_service.delete_panel(uuid)


@router.delete("/delete_link/{uuid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_link(
    unit_node_uuid: uuid_pkg.UUID,
    dashboard_panel_uuid: uuid_pkg.UUID,
    grafana_service: GrafanaService = Depends(get_grafana_service),
):
    return grafana_service.delete_link(unit_node_uuid, dashboard_panel_uuid)


@router.get("/oidc/authorize")
async def authorize(
    request: Request, client_id: str, redirect_uri: str, scope: str, state: str, nonce: Optional[str] = None
):
    session_cookie = request.cookies
    with get_hand_session() as db:
        user_service = get_user_service(db=db, jwt_token=session_cookie.get(CookieName.PEPEUNIT_GRAFANA.value, None))

        current_user = user_service.get(user_service.access_service.current_agent.uuid)
        org_id = create_org_if_not_exists(current_user)

        if current_user.grafana_org_id is None:
            current_user.grafana_org_id = str(org_id)
            user_service.user_repository.update(current_user.uuid, current_user)

    redis = await anext(get_redis_session())

    code = str(uuid_pkg.uuid4())
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


@router.get("/datasource/")
async def datasource(
    filters: DatasourceFilter = Depends(DatasourceFilter),
    grafana_service: GrafanaService = Depends(get_grafana_service),
):
    return grafana_service.get_datasource_data(filters)
