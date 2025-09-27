from fastapi import APIRouter

from app.routers.v1.grafana import router as grafana_router
from app.routers.v1.metrics_router import router as metrics_router
from app.routers.v1.permission_router import router as permission_router
from app.routers.v1.repo_router import router as repo_router
from app.routers.v1.repository_registry_router import (
    router as repository_registry_router,
)
from app.routers.v1.unit_node_router import router as unit_node_router
from app.routers.v1.unit_router import router as unit_router
from app.routers.v1.user_router import router as user_router

api_router = APIRouter()

include_api = api_router.include_router

routers = (
    (user_router, "users", "users"),
    (repository_registry_router, "repository_registry", "repository_registry"),
    (repo_router, "repos", "repos"),
    (unit_router, "units", "units"),
    (unit_node_router, "unit_nodes", "unit_nodes"),
    (metrics_router, "metrics", "metrics"),
    (permission_router, "permission", "permission"),
    (grafana_router, "grafana", "grafana"),
)

for router, prefix, tag in routers:
    if tag:
        include_api(router, prefix=f"/{prefix}", tags=[tag])
    else:
        include_api(router, prefix=f"/{prefix}")
