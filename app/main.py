import asyncio
import logging
import time
from contextlib import asynccontextmanager

import uvicorn
from aiokeydb import KeyDBClient
from fastapi import FastAPI
from fastapi_mqtt import FastMQTT, MQTTConfig
from prometheus_fastapi_instrumentator import Instrumentator
from strawberry import Schema
from strawberry.fastapi import GraphQLRouter

from app.configs.emqx import ControlEmqx
from app.configs.gql import get_graphql_context, get_repo_service
from app.configs.utils import (
    acquire_file_lock,
    is_valid_ip_address,
    wait_for_file_unlock,
)
from app.repositories.enum import GlobalPrefixTopic
from app.routers.v1.endpoints import api_router
from app.schemas.bot import *
from app.schemas.gql.mutation import Mutation
from app.schemas.gql.query import Query
from app.schemas.mqtt.topic import mqtt
from app.schemas.pydantic.shared import Root


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    FILE_INIT_LOCK = 'tmp/init_lock.lock'
    FILE_MQTT_RUN_LOCK = 'tmp/mqtt_run_lock.lock'

    init_lock = acquire_file_lock(FILE_INIT_LOCK)

    if init_lock:
        mqtt_run_lock = acquire_file_lock(FILE_MQTT_RUN_LOCK)

        control_emqx = ControlEmqx()
        control_emqx.delete_auth_hooks()
        control_emqx.set_file_auth_hook()
        control_emqx.set_http_auth_hook()
        control_emqx.set_redis_auth_hook()
        control_emqx.set_auth_cache_ttl()
        control_emqx.disable_default_listeners()
        control_emqx.set_tcp_listener_settings()
        control_emqx.set_global_mqtt_settings()

        KeyDBClient.init_session(uri=settings.mqtt_redis_auth_url)

        await KeyDBClient.async_wait_for_ready()
        await KeyDBClient.async_delete(settings.backend_token)

        backend_topics = (
            f'{settings.backend_domain}/+/+/+{GlobalPrefixTopic.BACKEND_SUB_PREFIX}',
            f'{settings.backend_domain}/+{GlobalPrefixTopic.BACKEND_SUB_PREFIX}',
        )

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

        db = next(get_session())

        try:
            repo_service = get_repo_service(InfoSubEntity({'db': db, 'jwt_token': None}))
            repo_service.sync_local_repo_storage()
        except Exception as ex:
            logging.error(ex)
        finally:
            db.close()

        mqtt_run_lock.close()

        logging.info(
            """
                                                         
                       :::::                            
                      ::::----                          
                      -:---=--                          
                      -:---=--                          
                  --------===+****                      
               -:-+========+++****+=                    
              :..::--===+++*****#*+===                  
            :..::::::----=**##*****++===                
          ::..:::-===---=-+****+===+++====              
        -:::::--+**##*+=--**+---=*####*+===             
      -::::-=-=**######*+=*+=--+*###*##**====           
      --::--**++**--+###***++**+*##*#*##**+=++          
      ==---=*#**#*==*###****+##*###***##***+++          
      ===---=*#*#*####*#####**#*#*#*###****+++          
      +*+----==*######################*#***#*+          
      *##=+=--=***###########################*          
    -:-=******#+***########################******#       
    ---=+***********************************######       
    ++********************************#######%####       
      *********==+********#########**########%          
        #*******++****++++*++*+####**#####%%            
           **########################%%%%               
           ###############%%%%%%%%%%%%%%                
                 ####%%%%%%%%%%%%%%
             
         _____                            _ _   
        |  __ \                          (_) |  
        | |__) |__ _ __   ___ _   _ _ __  _| |_ 
        |  ___/ _ \ '_ \ / _ \ | | | '_ \| | __|
        | |  |  __/ |_) |  __/ |_| | | | | | |_ 
        |_|   \___| .__/ \___|\__,_|_| |_|_|\__|
                  | |                           
                  |_|                           
                   """
        )

    async def run_mqtt_client(mqtt):
        logging.info(f'Connect to mqtt server: {settings.mqtt_host}:{settings.mqtt_port}')
        await mqtt.mqtt_startup()

        access = await KeyDBClient.async_hgetall(settings.backend_token)
        for k, v in access.items():
            logging.info(f'Redis set {k} access {v}')

        if init_lock:
            mqtt.client.subscribe(f'{settings.backend_domain}/+/+/+{GlobalPrefixTopic.BACKEND_SUB_PREFIX}')
            mqtt.client.subscribe(f'{settings.backend_domain}/+{GlobalPrefixTopic.BACKEND_SUB_PREFIX}')

    wait_for_file_unlock(FILE_MQTT_RUN_LOCK)

    await asyncio.get_event_loop().create_task(run_mqtt_client(mqtt), name='run_mqtt_client')

    yield

    if init_lock:
        init_lock.close()

    await mqtt.mqtt_shutdown()


app = FastAPI(
    title=settings.project_name,
    version=settings.version,
    openapi_url=f'{settings.backend_app_prefix}{settings.backend_api_v1_prefix}/openapi.json',
    docs_url=f'{settings.backend_app_prefix}/docs',
    debug=settings.backend_debug,
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
    prefix=f'{settings.backend_app_prefix}/graphql',
    include_in_schema=False,
)


@app.get(f'{settings.backend_app_prefix}', response_model=Root, tags=['status'])
async def root():
    return Root()


@app.post(f"{settings.backend_app_prefix}{settings.backend_api_v1_prefix}/bot")
async def bot_webhook(update: dict):
    telegram_update = types.Update(**update)
    await dp.feed_update(bot=bot, update=telegram_update)


Instrumentator().instrument(app).expose(app, endpoint=f'{settings.backend_app_prefix}/metrics')

app.include_router(api_router, prefix=f'{settings.backend_app_prefix}{settings.backend_api_v1_prefix}')

mqtt.init_app(app)

if __name__ == '__main__':
    uvicorn.run('app.main:app', port=8080, host='0.0.0.0', reload=True)
