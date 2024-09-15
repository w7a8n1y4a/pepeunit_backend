import asyncio
import logging
import time
from contextlib import asynccontextmanager

import uvicorn
from aiokeydb import KeyDBClient
from fastapi import FastAPI
from fastapi_mqtt import FastMQTT, MQTTConfig
from strawberry import Schema
from strawberry.fastapi import GraphQLRouter

from app import settings
from app.configs.gql import get_graphql_context
from app.configs.utils import (
    check_emqx_state,
    del_emqx_auth_hooks,
    is_valid_ip_address,
    set_emqx_auth_cache_ttl,
    set_http_emqx_auth_hook,
    set_redis_emqx_auth_hook,
)
from app.routers.v1.endpoints import api_router
from app.schemas.bot import *
from app.schemas.gql.mutation import Mutation
from app.schemas.gql.query import Query
from app.schemas.mqtt.topic import mqtt
from app.schemas.pydantic.shared import Root


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    check_emqx_state()
    del_emqx_auth_hooks()
    set_http_emqx_auth_hook()
    set_redis_emqx_auth_hook()
    set_emqx_auth_cache_ttl()

    KeyDBClient.init_session(uri=settings.redis_mqtt_auth_url)

    await KeyDBClient.async_wait_for_ready()
    await KeyDBClient.async_delete(settings.backend_token)

    backend_topics = (f'{settings.backend_domain}/+/+/+/pepeunit', f'{settings.backend_domain}/+/pepeunit')

    async def hset_emqx_auth_keys(KeyDBClient, topic):
        await KeyDBClient.async_hset(f'mqtt_acl:{settings.backend_token}', topic, 'all')

    await asyncio.gather(*[hset_emqx_auth_keys(KeyDBClient, topic) for topic in backend_topics])

    async def run_polling_bot(dp, bot):
        logging.info(f'Delete webhook before run polling')
        await bot.delete_webhook()

        logging.info(f'Run polling')
        await dp.start_polling(bot)

    if is_valid_ip_address(settings.backend_domain):
        asyncio.get_event_loop().create_task(run_polling_bot(dp, bot), name='run_polling_bot')

    logging.info(f'Get current TG bot webhook info')

    if not is_valid_ip_address(settings.backend_domain):
        webhook_url = f'{settings.backend_link_prefix_and_v1}/bot'

        logging.info(f'Delete webhook before set new webhook')
        await bot.delete_webhook()

        logging.info(f'Set new TG bot webhook url: {webhook_url}')
        await bot.set_webhook(url=webhook_url, drop_pending_updates=True)

        logging.info(f'Success set TG bot webhook url')

    async def run_mqtt_client(mqtt):
        logging.info(f'Connect to mqtt server: {settings.mqtt_host}:{settings.mqtt_port}')
        await mqtt.mqtt_startup()

        access = await KeyDBClient.async_hgetall(settings.backend_token)
        for k, v in access.items():
            logging.info(f'Redis set {k} access {v}')

        mqtt.client.subscribe(f'{settings.backend_domain}/+/+/+/pepeunit')
        mqtt.client.subscribe(f'{settings.backend_domain}/+/pepeunit')

    await asyncio.get_event_loop().create_task(run_mqtt_client(mqtt), name='run_mqtt_client')
    yield
    await mqtt.mqtt_shutdown()


app = FastAPI(
    title=settings.project_name,
    version=settings.version,
    openapi_url=f'{settings.app_prefix}{settings.api_v1_prefix}/openapi.json',
    docs_url=f'{settings.app_prefix}/docs',
    debug=settings.debug,
    lifespan=_lifespan,
)


schema = Schema(query=Query, mutation=Mutation)
graphql = GraphQLRouter(
    schema,
    graphiql=True,
    context_getter=get_graphql_context,
)


app.include_router(
    graphql,
    prefix=f'{settings.app_prefix}/graphql',
    include_in_schema=False,
)


@app.get(f'{settings.app_prefix}', response_model=Root, tags=['status'])
async def root():
    return Root()


@app.post(f"{settings.app_prefix}{settings.api_v1_prefix}/bot")
async def bot_webhook(update: dict):
    telegram_update = types.Update(**update)
    await dp.feed_update(bot=bot, update=telegram_update)


app.include_router(api_router, prefix=f'{settings.app_prefix}{settings.api_v1_prefix}')

mqtt.init_app(app)

if __name__ == '__main__':
    uvicorn.run('app.main:app', port=8080, host='0.0.0.0', reload=True)
