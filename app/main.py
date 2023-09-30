import uvicorn
from fastapi import FastAPI
from telebot import types

from app import settings
from app.api.api_v1.endpoints import api_router
from app.core.models import Root

from app.modules.bot import *


app = FastAPI(
    title=settings.project_name,
    version=settings.version,
    openapi_url=f"{settings.app_prefix}{settings.api_v1_prefix}/openapi.json",
    docs_url=f"{settings.app_prefix}/docs",
    debug=settings.debug,
)


@app.get(settings.app_prefix, response_model=Root, tags=["status"])
def root():
    return {
        "name": settings.project_name,
        "version": settings.version,
        "description": settings.description,
        "swagger": f"{settings.app_prefix}/docs",
    }


app.include_router(api_router, prefix=f'{settings.app_prefix}{settings.api_v1_prefix}')

if __name__ == '__main__':
    uvicorn.run("main:app", port=8080, host="0.0.0.0", reload=True)
