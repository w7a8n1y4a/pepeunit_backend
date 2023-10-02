from fastapi import APIRouter
from app.modules.devices.api import router as devices_router

api_router = APIRouter()

include_api = api_router.include_router

routers = ((devices_router, "devices", "devices"),)

for router, prefix, tag in routers:

    if tag:
        include_api(router, prefix=f"/{prefix}", tags=[tag])
    else:
        include_api(router, prefix=f"/{prefix}")
