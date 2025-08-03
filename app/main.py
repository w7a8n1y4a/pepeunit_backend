import asyncio
import json
import logging
from contextlib import asynccontextmanager

import aiogram.exceptions
import httpx
import uvicorn
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.base import DefaultKeyBuilder
from aiogram.fsm.storage.redis import RedisStorage
from clickhouse_migrations.clickhouse_cluster import ClickhouseCluster
from fastapi import FastAPI, Request
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from strawberry import Schema
from strawberry.fastapi import GraphQLRouter

from app import settings
from app.configs.db import get_hand_session
from app.configs.emqx import ControlEmqx
from app.configs.errors import CustomException
from app.configs.gql import get_graphql_context
from app.configs.redis import get_redis_session
from app.configs.rest import get_repository_registry_service
from app.configs.utils import (
    acquire_file_lock,
    is_valid_ip_address,
    recreate_directory,
    wait_for_file_unlock,
)
from app.dto.agent.abc import AgentBackend
from app.dto.enum import GlobalPrefixTopic
from app.routers.v1.endpoints import api_router
from app.schemas.bot.error import error_router
from app.schemas.bot.info import info_router
from app.schemas.bot.repo_bot_router import RepoBotRouter
from app.schemas.bot.repository_registry_bot_router import RepositoryRegistryBotRouter
from app.schemas.bot.start_help import base_router
from app.schemas.bot.unit_bot_router import UnitBotRouter
from app.schemas.bot.unit_log_bot_router import UnitLogBotRouter
from app.schemas.bot.unit_node_bot_router import UnitNodeBotRouter
from app.schemas.gql.mutation import Mutation
from app.schemas.gql.query import Query
from app.schemas.mqtt.topic import mqtt
from app.schemas.pydantic.shared import Root

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s - %(asctime)s - %(message)s",
)
logging.getLogger("httpx").setLevel(logging.INFO)


recreate_directory(settings.prometheus_multiproc_dir)


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    FILE_INIT_LOCK = 'tmp/init_lock.lock'
    FILE_MQTT_RUN_LOCK = 'tmp/mqtt_run_lock.lock'

    init_lock = acquire_file_lock(FILE_INIT_LOCK)

    redis = await anext(get_redis_session())

    if init_lock:

        mqtt_run_lock = acquire_file_lock(FILE_MQTT_RUN_LOCK)

        clickhouse_cluster = ClickhouseCluster(
            settings.clickhouse_connection.host,
            settings.clickhouse_connection.user,
            settings.clickhouse_connection.password,
        )
        clickhouse_cluster.migrate(
            settings.clickhouse_connection.database,
            './clickhouse/migrations',
            cluster_name=None,
            create_db_if_no_exists=True,
            multi_statement=True,
        )

        control_emqx = ControlEmqx()
        control_emqx.delete_auth_hooks()
        control_emqx.set_file_auth_hook()
        control_emqx.set_http_auth_hook()
        control_emqx.set_redis_auth_hook()
        control_emqx.set_auth_cache_ttl()
        control_emqx.disable_default_listeners()
        control_emqx.set_tcp_listener_settings()
        control_emqx.set_global_mqtt_settings()

        backend_topics = (f'{settings.backend_domain}/+/+/+{GlobalPrefixTopic.BACKEND_SUB_PREFIX}',)

        async def hset_emqx_auth_keys(redis_client, topic):
            token = AgentBackend(name=settings.backend_domain).generate_agent_token()
            await redis_client.hset(f'mqtt_acl:{token}', topic, 'all')

        await asyncio.gather(*[hset_emqx_auth_keys(redis, topic) for topic in backend_topics])

        async def run_polling_bot(dp, bot):
            logging.info(f'Delete webhook before run polling')
            await bot.delete_webhook()

            logging.info(f'Run polling')
            await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

        async def run_webhook_bot(dp, bot):
            webhook_url = f'{settings.backend_link_prefix_and_v1}/bot'

            logging.info(f'Delete webhook before set new webhook')
            await bot.delete_webhook()

            inc = 0
            while True:
                result = httpx.post(
                    f'{settings.backend_link_prefix_and_v1}/bot', headers={'Content-Type': 'application/json'}
                )
                if result.status_code == 422:
                    break

                await asyncio.sleep(2)

                if inc > 10:
                    raise Exception('Webhook route not valid')

                inc += 1

            try:
                await bot.set_webhook(
                    url=webhook_url, drop_pending_updates=True, allowed_updates=dp.resolve_used_update_types()
                )
                logging.info(f'Success set TG bot webhook url')
            except aiogram.exceptions.TelegramBadRequest as e:
                print(e.__dict__)
                logging.info(f'Error set TG bot webhook url')

        if is_valid_ip_address(settings.backend_domain):
            asyncio.get_event_loop().create_task(run_polling_bot(dp, bot), name='run_polling_bot')
        else:
            asyncio.get_event_loop().create_task(run_webhook_bot(dp, bot), name='run_webhook_bot')

        with get_hand_session() as db:
            repository_registry_service = get_repository_registry_service(
                db, AgentBackend(name=settings.backend_domain).generate_agent_token()
            )
            repository_registry_service.sync_local_repository_storage()

        mqtt_run_lock.close()

        logging.info(
            f"""
            
                           ........:                                   
                          :......::-                                   
                           .....::.:                                   
                           .....::.-                                   
                      :.........::.-****                               
                    :........::::--==++###%                            
                  :::-++*++=======++*#@@%%-::                          
                ....:-=---==++******###%%*-...:                        
              :....:--===++=*=+**%@@%@%%%%*+:..:                       
            :....::=====+====+==*##%@%%%#*##+=...:                     
          -...........:-===++*=++**#%*:....::---...:                   
         :......-..:*##%%*+++===+#*-.:-..+#%%%#*+:...:                 
       :......=..++*##%%%%#**++--=..-.--*##%%*%@#+=....-               
      :..:-:.+-+=+#%%***+#@#*=---..+:=**+%@%%*%@@*+=-...:              
     =--===-.%%=#*#%-.=:+@@%**==-::%%#==#@@#%@@+@%**+=:::              
     =-=====.+@%%+@@%:.-#@@##***+-:%@%*%@%@%%=%@@#++::-::              
     =--====-.#@@*@+@@*@@@#***#**#-:%@*%%+@=@*@@#*==-..::              
     ==+*=+++=::#@@@@@@@########*#%==+%@@@@@@@#**++++*+::-             
     *@*+++++++++****#####%##%###%#%%%%#########*##+==*#--             
     -*@%**==+=+*#=+**###%%%%####%%##%%%%%%%#%%%#####@@%=+             
  :::-=--+%%@*##*.-.*#####%%%########%%%%%%%###%%@@%*++=+****          
  ....:---------==***#%%%%%*%#%%#%%%%%%%%%#*++=====+**#######%         
  ....:-:::-=====-----------------------===+++***+++*#%@@%###%         
  :--=:=++++====---::::---------===========++*##%@@@@@@@@@@@@@         
     =--+*++++***+=+*****###########%%%%%%%%%#%%%#@@@@@@@@             
       +==++++**+...:*=+=*=+==*++##++=+++#%-:-*%#%@@@@@@               
          %#*****#####*##*-+-=*==#--+#**%*%%%%@@@@@@@                  
            *##%@@@@@@@%%%%%%%%%%%%%%@@@@@@@@@@@@@@                    
            *###%%@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@                    
                %%@@@@@@@@@@@@@@@@@@@@@@@@@@@@       
             _____                            _ _   
            |  __ \                          (_) |  
            | |__) |__ _ __   ___ _   _ _ __  _| |_ 
            |  ___/ _ \ '_ \ / _ \ | | | '_ \| | __|
            | |  |  __/ |_) |  __/ |_| | | | | | |_ 
            |_|   \___| .__/ \___|\__,_|_| |_|_|\__|
                      | |                           
                      |_|   
                   
     v{settings.version} - {settings.license}
     Federated IoT Platform
     Front: {settings.backend_link}
     REST:  {settings.backend_link_prefix}/docs
     GQL:   {settings.backend_link_prefix}/graphql
     TG:    {settings.telegram_bot_link}
     Docs:  https://pepeunit.com
            """
        )

    async def run_mqtt_client(mqtt, redis_client):
        logging.info(f'Connect to mqtt server: {settings.mqtt_host}:{settings.mqtt_port}')
        await mqtt.mqtt_startup()

        token = AgentBackend(name=settings.backend_domain).generate_agent_token()
        access = await redis_client.hgetall(token)
        for k, v in access.items():
            logging.info(f'Redis set {k} access {v}')

    wait_for_file_unlock(FILE_MQTT_RUN_LOCK)

    await asyncio.get_event_loop().create_task(run_mqtt_client(mqtt, redis), name='run_mqtt_client')

    yield

    if init_lock:
        init_lock.close()

    await mqtt.mqtt_shutdown()


class CustomExceptionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except CustomException as e:
            return JSONResponse(
                status_code=e.status_code,
                content={"detail": e.message},
            )
        except StarletteHTTPException as e:
            return await super().dispatch(request, call_next)


app = FastAPI(
    title=settings.project_name,
    version=settings.version,
    openapi_url=f'{settings.backend_app_prefix}{settings.backend_api_v1_prefix}/openapi.json',
    docs_url=f'{settings.backend_app_prefix}/docs',
    debug=settings.backend_debug,
    lifespan=_lifespan,
)

app.add_middleware(CustomExceptionMiddleware)

schema = Schema(query=Query, mutation=Mutation)
graphql = GraphQLRouter(schema, graphiql=True, context_getter=get_graphql_context, multipart_uploads_enabled=True)


app.include_router(
    graphql,
    prefix=f'{settings.backend_app_prefix}/graphql',
    include_in_schema=False,
)


@app.get(f'{settings.backend_app_prefix}', response_model=Root, tags=['status'])
async def root():
    return Root()


def custom_json_dumps(obj: dict, **kwargs):

    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, BaseModel):
                obj[k] = v.model_dump()

    return json.dumps(obj, **kwargs)


bot = Bot(token=settings.telegram_token)
storage = RedisStorage.from_url(
    settings.redis_url, key_builder=DefaultKeyBuilder(with_destiny=True), json_dumps=custom_json_dumps
)
dp = Dispatcher(bot=bot, storage=storage)


dp.include_router(info_router)
dp.include_router(base_router)
dp.include_router(RepositoryRegistryBotRouter().router)
dp.include_router(RepoBotRouter().router)
dp.include_router(UnitBotRouter().router)
dp.include_router(UnitNodeBotRouter().router)
dp.include_router(UnitLogBotRouter().router)
dp.include_router(error_router)


@app.post(f"{settings.backend_app_prefix}{settings.backend_api_v1_prefix}/bot")
async def bot_webhook(update: dict):
    telegram_update = types.Update(**update)
    await dp.feed_update(bot=bot, update=telegram_update)


Instrumentator().instrument(app).expose(app, endpoint=f'{settings.backend_app_prefix}/metrics')

app.include_router(api_router, prefix=f'{settings.backend_app_prefix}{settings.backend_api_v1_prefix}')

mqtt.init_app(app)

if __name__ == '__main__':
    uvicorn.run('app.main:app', port=8080, host='0.0.0.0', reload=True)
