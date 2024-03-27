import uvicorn
import datetime
import time

from fastapi import FastAPI, WebSocket
from fastapi_mqtt import FastMQTT, MQTTConfig
from strawberry import Schema
from strawberry.fastapi import GraphQLRouter

from app import settings
from app.routers.v1.endpoints import api_router
from app.configs.gql import get_graphql_context
from app.schemas.gql.mutation import Mutation
from app.schemas.gql.query import Query
from app.schemas.pydantic.shared import Root

app = FastAPI(
    title=settings.project_name,
    version=settings.version,
    openapi_url=f'{settings.app_prefix}{settings.api_v1_prefix}/openapi.json',
    docs_url=f'{settings.app_prefix}/docs',
    debug=settings.debug,
)

# GraphQL Schema and Application Instance
schema = Schema(query=Query, mutation=Mutation)
graphql = GraphQLRouter(
    schema,
    graphiql=True,
    context_getter=get_graphql_context,
)

# Integrate GraphQL Application to the Core one
app.include_router(
    graphql,
    prefix=f'{settings.app_prefix}/graphql',
    include_in_schema=False,
)

mqtt_config = MQTTConfig(
    host=settings.mqtt_host,
    port=settings.mqtt_port,
    keepalive=settings.mqtt_keepalive,
    username=settings.mqtt_username,
    password=settings.mqtt_password,
)

mqtt = FastMQTT(config=mqtt_config)

mqtt.init_app(app)


@app.websocket('/ws')
async def websocket_endpoint(websocket: WebSocket):
    print('123')
    try:
        await websocket.accept()
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(str(time.time()))
    except Exception as e:
        await websocket.close()


@mqtt.on_connect()
def connect(client, flags, rc, properties):
    mqtt.client.subscribe('co2')  # subscribing mqtt topic
    print('Connected: ', client, flags, rc, properties)


@mqtt.on_message()
async def message(client, topic, payload, qos, properties):
    print('Received message: ', topic, payload.decode(), qos, properties)


@mqtt.subscribe('co2')
async def message_to_topic(client, topic, payload, qos, properties):
    print(f'{datetime.datetime.utcnow()}', topic, payload.decode(), qos, properties)


@mqtt.subscribe('co2', qos=1)
async def message_to_topic_with_high_qos(client, topic, payload, qos, properties):
    print(f'{datetime.datetime.utcnow()}', topic, payload.decode(), qos, properties)


@mqtt.on_disconnect()
def disconnect(client, packet, exc=None):
    print('Disconnected')


@mqtt.on_subscribe()
def subscribe(client, mid, qos, properties):
    print('subscribed', client, mid, qos, properties)


@app.get(f'{settings.app_prefix}', response_model=Root, tags=['status'])
def root():
    return {
        'name': settings.project_name,
        'version': settings.version,
        'description': settings.description,
        'swagger': f'{settings.app_prefix}/docs',
        'graphql': f'{settings.app_prefix}/graphql',
    }


app.include_router(api_router, prefix=f'{settings.app_prefix}{settings.api_v1_prefix}')

if __name__ == '__main__':
    uvicorn.run('app.main:app', port=8080, host='0.0.0.0', reload=True)
