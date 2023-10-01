from fastapi import APIRouter

from app.modules.files.api import router as files_router

api_router = APIRouter()

include_api = api_router.include_router

routers = ((files_router, "files", "files"),)

for router, prefix, tag in routers:

    if tag:
        include_api(router, prefix=f"/{prefix}", tags=[tag])
    else:
        include_api(router, prefix=f"/{prefix}")
