import json
import logging
from contextlib import asynccontextmanager

from aiogram import Dispatcher, types
from aiogram.fsm.storage.base import DefaultKeyBuilder
from aiogram.fsm.storage.redis import RedisStorage
from fastapi import FastAPI, Request
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app import BackendLogLevel, runtime, settings
from app.configs.errors import CustomException
from app.configs.logging_config import setup_logging
from app.configs.utils import recreate_directory
from app.routers.v1.endpoints import api_router
from app.schemas.bot.control_bot_router import ControlBotRouter
from app.schemas.bot.dashboard_bot_router import DashboardBotRouter
from app.schemas.bot.error import error_router
from app.schemas.bot.info import info_router
from app.schemas.bot.notification_bot_router import NotificationBotRouter
from app.schemas.bot.peer_bot_router import PeerBotRouter
from app.schemas.bot.repo_bot_router import (
    RepoBotRouter,
)
from app.schemas.bot.start_help import base_router
from app.schemas.bot.unit_bot_router import UnitBotRouter
from app.schemas.bot.unit_io_bot_router import UnitIOBotRouter
from app.schemas.bot.unit_log_bot_router import UnitLogBotRouter
from app.schemas.bot.utils import build_telegram_bot
from app.schemas.mqtt.topic import mqtt
from app.services.startup_service import StartupService

setup_logging()


if runtime.get().pu_ff_prometheus_enable:
    recreate_directory(settings.pu_prometheus_multiproc_dir)


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    startup = StartupService(
        _app,
        mqtt,
        bot if runtime.get().pu_ff_telegram_bot_enable else None,
        dp if runtime.get().pu_ff_telegram_bot_enable else None,
    )
    await startup.start()
    yield
    await startup.stop()


class CustomExceptionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except CustomException as e:
            return JSONResponse(
                status_code=e.status_code,
                content={"detail": e.message, "error_code": e.error_code},
            )
        except StarletteHTTPException:
            return await super().dispatch(request, call_next)


app = FastAPI(
    title=settings.project_name,
    version=settings.version,
    openapi_url=f"{settings.pu_app_prefix}{settings.pu_api_v1_prefix}/openapi.json",
    docs_url=f"{settings.pu_app_prefix}/docs",
    debug=runtime.get().pu_instance_log_min_level == BackendLogLevel.DEBUG,
    lifespan=_lifespan,
)

app.add_middleware(CustomExceptionMiddleware)


def custom_json_dumps(obj: dict, **kwargs):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, BaseModel):
                obj[k] = v.model_dump()

    return json.dumps(obj, **kwargs)


bot = None
dp = None
if runtime.get().pu_ff_telegram_bot_enable:
    bot = build_telegram_bot()

if bot is not None:
    storage = RedisStorage.from_url(
        settings.pu_redis_url,
        key_builder=DefaultKeyBuilder(with_destiny=True),
        json_dumps=custom_json_dumps,
    )
    dp = Dispatcher(bot=bot, storage=storage)

    dp.include_router(info_router)
    dp.include_router(ControlBotRouter().router)
    dp.include_router(PeerBotRouter().router)
    dp.include_router(NotificationBotRouter().router)
    dp.include_router(base_router)
    dp.include_router(RepoBotRouter().router)
    dp.include_router(UnitBotRouter().router)
    dp.include_router(UnitIOBotRouter().router)
    dp.include_router(UnitLogBotRouter().router)
    if runtime.get().pu_ff_grafana_integration_enable:
        dp.include_router(DashboardBotRouter().router)
    dp.include_router(error_router)

    @app.post(f"{settings.pu_app_prefix}{settings.pu_api_v1_prefix}/bot")
    async def bot_webhook(update: dict):
        if not runtime.get().pu_ff_telegram_bot_enable:
            return {"status": "disabled"}
        try:
            telegram_update = types.Update(**update)
            await dp.feed_update(bot=bot, update=telegram_update)
        except Exception as e:
            logging.error(f"Error processing telegram update: {e}")
            # Return 200 to prevent telegram from retrying
            return {"status": "error", "message": str(e)}


if runtime.get().pu_ff_prometheus_enable:
    Instrumentator().instrument(app).expose(
        app, endpoint=f"{settings.pu_app_prefix}/metrics"
    )

app.include_router(
    api_router,
    prefix=f"{settings.pu_app_prefix}{settings.pu_api_v1_prefix}",
)

mqtt.init_app(app)
