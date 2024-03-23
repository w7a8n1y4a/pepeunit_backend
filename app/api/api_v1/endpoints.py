from fastapi import APIRouter
# from app.modules.repo.api import router as repo_router
# from app.modules.unit.api import router as unit_router

from app.routers.v1.user_router import router as user_router

api_router = APIRouter()

include_api = api_router.include_router

routers = (
    (user_router, "users", "users"),
    # (repo_router, "repos", "repos"),
    # (unit_router, "units", "units"),
)

for router, prefix, tag in routers:
    if tag:
        include_api(router, prefix=f"/{prefix}", tags=[tag])
    else:
        include_api(router, prefix=f"/{prefix}")
