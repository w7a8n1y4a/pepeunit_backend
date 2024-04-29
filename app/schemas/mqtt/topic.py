import time

from fastapi_mqtt import FastMQTT, MQTTConfig

from app import settings
from app.configs.db import get_session
from app.configs.redis import get_redis_session
from app.domain.unit_model import Unit
from app.domain.unit_node_model import UnitNode
from app.repositories.enum import ReservedOutputBaseTopic
from app.repositories.unit_node_repository import UnitNodeRepository
from app.repositories.unit_repository import UnitRepository
from app.schemas.mqtt.utils import get_topic_split

mqtt_config = MQTTConfig(
    host=settings.mqtt_host,
    port=settings.mqtt_port,
    keepalive=settings.mqtt_keepalive,
    username=settings.mqtt_username,
    password=settings.mqtt_password,
)

mqtt = FastMQTT(config=mqtt_config)

# todo refactor оценить вынос функционала в отдельный сервис unit_node_service


@mqtt.subscribe('output/+/#')
async def message_to_topic(client, topic, payload, qos, properties):
    start_time = time.perf_counter()

    print(f'{str(topic)}, {str(payload.decode())}')

    redis = await anext(get_redis_session())

    redis_topic_value = await redis.get(str(topic))

    if redis_topic_value != str(payload.decode()):
        # todo разобраться как правильно построить сессию для кэширования, в данной конфигурации успевает обрабатываться только 100 запросов в секунду на весь бекенд

        await redis.set(str(topic), str(payload.decode()))

        destination, unit_uuid, topic_name, *_ = get_topic_split(topic)

        db = next(get_session())

        # todo refactor, uuid в схему на стороне физического unit, может решить проблему поиска в базе
        unit_node_repository = UnitNodeRepository(db)
        unit_node = unit_node_repository.get_output_topic(unit_uuid, UnitNode(topic_name=topic_name))
        unit_node.state = str(payload.decode())
        unit_node_repository.update(unit_node.uuid, unit_node)

        db.close()

    print(f'{time.perf_counter() - start_time}')


@mqtt.subscribe('output_base/+/#')
async def message_to_topic(client, topic, payload, qos, properties):
    destination, unit_uuid, topic_name, *_ = get_topic_split(topic)

    if topic_name == ReservedOutputBaseTopic.STATE:
        db = next(get_session())
        unit_repository = UnitRepository(db)
        unit_repository.update(unit_uuid, Unit(unit_state_dict=str(payload.decode())))

        db.close()

    print(f'{str(topic)}, {str(payload.decode())}')


@mqtt.on_disconnect()
def disconnect(client, packet, exc=None):
    print('Disconnected')


@mqtt.on_subscribe()
def subscribe(client, mid, qos, properties):
    print('subscribed', client, mid, qos, properties)
