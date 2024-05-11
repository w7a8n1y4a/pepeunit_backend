import uvicorn
from aiogram import Dispatcher

from fastapi import FastAPI
from strawberry import Schema
from strawberry.fastapi import GraphQLRouter

from app import settings
from app.routers.v1.endpoints import api_router
from app.configs.gql import get_graphql_context
from app.schemas.gql.mutation import Mutation
from app.schemas.gql.query import Query
from app.schemas.pydantic.shared import Root
from app.schemas.bot import *
from app.schemas.mqtt.topic import mqtt

app = FastAPI(
    title=settings.project_name,
    version=settings.version,
    openapi_url=f'{settings.app_prefix}{settings.api_v1_prefix}/openapi.json',
    docs_url=f'{settings.app_prefix}/docs',
    debug=settings.debug,
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


@app.on_event("startup")
async def on_startup():

    webhook_info = await bot.get_webhook_info()
    webhook_url = f'https://{settings.backend_domain}{settings.app_prefix}{settings.api_v1_prefix}/bot'

    if webhook_info.url != webhook_url:
        await bot.set_webhook(
            url=webhook_url
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
