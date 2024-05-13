import json
import time

from fastapi_mqtt import FastMQTT, MQTTConfig

from app import settings
from app.configs.db import get_session
from app.domain.unit_model import Unit
from app.repositories.enum import ReservedOutputBaseTopic
from app.repositories.unit_repository import UnitRepository
from app.schemas.mqtt.utils import get_topic_split
from app.services.unit_node_service import UnitNodeService

mqtt_config = MQTTConfig(
    host=settings.mqtt_host,
    port=settings.mqtt_port,
    keepalive=settings.mqtt_keepalive,
    username=settings.mqtt_username,
    password=settings.mqtt_password,
)

mqtt = FastMQTT(config=mqtt_config)


@mqtt.subscribe(f'{settings.backend_domain}/+/+/+/pepeunit')
async def message_to_topic(client, topic, payload, qos, properties):
    start_time = time.perf_counter()

    print(f'{str(payload.decode())}')

    backend_domain, destination, unit_uuid, topic_name, *_ = get_topic_split(topic)

    topic_name += '/pepeunit'

    if destination in ['input', 'output']:

        # redis = await from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
        # redis_topic_value = await redis.get(str(topic))
        #
        # if redis_topic_value != str(payload.decode()):
        #     # todo refactor разобраться как правильно построить сессию для кэширования, в данной конфигурации успевает обрабатываться только 100 запросов в секунду на весь бекенд
        #
        #     await redis.set(str(topic), str(payload.decode()))

        db = next(get_session())
        unit_node_service = UnitNodeService(db)

        unit_node_service.set_state(unit_uuid, topic_name, destination.capitalize(), str(payload.decode()))
        db.close()

        # await redis.close()
        # await redis.connection_pool.disconnect()

    elif destination == 'output_base':
        if topic_name == ReservedOutputBaseTopic.STATE+'/pepeunit':
            db = next(get_session())
            unit_repository = UnitRepository(db)

            unit_state_dict = json.loads(payload.decode())

            unit_repository.update(
                unit_uuid,
                Unit(unit_state_dict=str(payload.decode()), current_commit_version=unit_state_dict['commit_version']),
            )
            db.close()

    print(f'{time.perf_counter() - start_time}')


@mqtt.on_disconnect()
def disconnect(client, packet, exc=None):
    print('Disconnected')


@mqtt.on_subscribe()
def subscribe(client, mid, qos, properties):
    print('subscribed', client, mid, qos, properties)
