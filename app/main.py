import json
import logging
from contextlib import asynccontextmanager

from aiogram import Bot, Dispatcher, types
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.fsm.storage.base import DefaultKeyBuilder
from aiogram.fsm.storage.redis import RedisStorage
from fastapi import FastAPI, Request
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from strawberry import Schema
from strawberry.fastapi import GraphQLRouter

from app import settings
from app.configs.errors import CustomException
from app.configs.gql import get_graphql_context
from app.configs.logging_config import setup_logging
from app.configs.utils import recreate_directory
from app.repositories.instance_cache_repository import InstanceCacheRepository
from app.routers.v1.endpoints import api_router
from app.schemas.bot.control_bot_router import ControlBotRouter
from app.schemas.bot.dashboard_bot_router import DashboardBotRouter
from app.schemas.bot.error import error_router
from app.schemas.bot.info import info_router
from app.schemas.bot.instance_bot_router import InstanceBotRouter
from app.schemas.bot.operation_task_bot_router import OperationTaskBotRouter
from app.schemas.bot.repo_bot_router import RepoBotRouter
from app.schemas.bot.repository_registry_bot_router import (
    RepositoryRegistryBotRouter,
)
from app.schemas.bot.start_help import base_router
from app.schemas.bot.unit_bot_router import UnitBotRouter
from app.schemas.bot.unit_log_bot_router import UnitLogBotRouter
from app.schemas.bot.unit_node_bot_router import UnitNodeBotRouter
from app.schemas.gql.mutation import Mutation
from app.schemas.gql.query import Query
from app.schemas.mqtt.topic import mqtt
from app.services.startup_service import StartupService

setup_logging()


if settings.pu_ff_prometheus_enable:
    recreate_directory(settings.pu_prometheus_multiproc_dir)


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    runtime = StartupService(
        _app,
        mqtt,
        bot if settings.pu_ff_telegram_bot_enable else None,
        dp if settings.pu_ff_telegram_bot_enable else None,
    )
    await runtime.start()
    yield
    await runtime.stop()


class CustomExceptionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except CustomException as e:
            return JSONResponse(
                status_code=e.status_code, content={"detail": e.message}
            )
        except StarletteHTTPException:
            return await super().dispatch(request, call_next)


app = FastAPI(
    title=settings.project_name,
    version=settings.version,
    openapi_url=f"{settings.pu_app_prefix}{settings.pu_api_v1_prefix}/openapi.json",
    docs_url=f"{settings.pu_app_prefix}/docs",
    debug=settings.pu_min_log_level == "DEBUG",
    lifespan=_lifespan,
)
app.state.instance_cache = InstanceCacheRepository()

app.add_middleware(CustomExceptionMiddleware)

schema = Schema(query=Query, mutation=Mutation)
graphql = GraphQLRouter(
    schema,
    graphiql=True,
    context_getter=get_graphql_context,
    multipart_uploads_enabled=True,
)


app.include_router(
    graphql,
    prefix=f"{settings.pu_app_prefix}/graphql",
    include_in_schema=False,
)


def custom_json_dumps(obj: dict, **kwargs):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, BaseModel):
                obj[k] = v.model_dump()

    return json.dumps(obj, **kwargs)


def _build_telegram_bot_session() -> AiohttpSession | None:
    if not settings.pu_telegram_proxy_url:
        return None

    logging.info("Telegram bot will use proxy")

    return AiohttpSession(proxy=settings.pu_telegram_proxy_url)


if settings.pu_ff_telegram_bot_enable:
    _telegram_session = _build_telegram_bot_session()
    bot = (
        Bot(token=settings.pu_telegram_token, session=_telegram_session)
        if _telegram_session is not None
        else Bot(token=settings.pu_telegram_token)
    )
    storage = RedisStorage.from_url(
        settings.pu_redis_url,
        key_builder=DefaultKeyBuilder(with_destiny=True),
        json_dumps=custom_json_dumps,
    )
    dp = Dispatcher(bot=bot, storage=storage)

    dp.include_router(info_router)
    dp.include_router(ControlBotRouter().router)
    dp.include_router(InstanceBotRouter().router)
    dp.include_router(OperationTaskBotRouter().router)
    dp.include_router(base_router)
    dp.include_router(RepositoryRegistryBotRouter().router)
    dp.include_router(RepoBotRouter().router)
    dp.include_router(UnitBotRouter().router)
    dp.include_router(UnitNodeBotRouter().router)
    dp.include_router(UnitLogBotRouter().router)
    if settings.pu_ff_grafana_integration_enable:
        dp.include_router(DashboardBotRouter().router)
    dp.include_router(error_router)

    @app.post(f"{settings.pu_app_prefix}{settings.pu_api_v1_prefix}/bot")
    async def bot_webhook(update: dict):
        try:
            telegram_update = types.Update(**update)
            await dp.feed_update(bot=bot, update=telegram_update)
        except Exception as e:
            logging.error(f"Error processing telegram update: {e}")
            # Return 200 to prevent telegram from retrying
            return {"status": "error", "message": str(e)}


if settings.pu_ff_prometheus_enable:
    Instrumentator().instrument(app).expose(
        app, endpoint=f"{settings.pu_app_prefix}/metrics"
    )

app.include_router(
    api_router,
    prefix=f"{settings.pu_app_prefix}{settings.pu_api_v1_prefix}",
)

mqtt.init_app(app)
