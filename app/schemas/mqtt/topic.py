import time

from fastapi_mqtt import FastMQTT, MQTTConfig

from app import settings
from app.configs.db import get_session
from app.configs.redis import get_redis_session
from app.domain.test_model import Test

mqtt_config = MQTTConfig(
    host=settings.mqtt_host,
    port=settings.mqtt_port,
    keepalive=settings.mqtt_keepalive,
    username=settings.mqtt_username,
    password=settings.mqtt_password,
)

mqtt = FastMQTT(config=mqtt_config)


# todo разделить на input и output
# cписок подписок на устройстве должен обновляться

@mqtt.subscribe('output/+/#')
async def message_to_topic(client, topic, payload, qos, properties):
    start_time = time.perf_counter()

    print(f'{str(topic)}, {str(payload.decode())}')

    redis = await anext(get_redis_session())

    redis_topic_value = await redis.get(str(topic))


    if redis_topic_value != str(payload.decode()):

        # todo разобраться как правильно построить сессию для кэширования, в данной конфигурации успевает обрабатываться только 100 запросов в секунду на весь бекенд

        await redis.set(str(topic), str(payload.decode()))

        db = next(get_session())

        test = Test(value=f'{str(topic)}, {str(payload.decode())}')
        test.uuid = '7af0cb07-a0d0-41a8-81e9-251457e1a9d0'

        db.merge(test)

        db.commit()

    print(f'{time.perf_counter() - start_time}')

@mqtt.subscribe('output_base/+/#')
async def message_to_topic(client, topic, payload, qos, properties):

    print(f'{str(topic)}, {str(payload.decode())}')


@mqtt.on_disconnect()
def disconnect(client, packet, exc=None):
    print('Disconnected')


@mqtt.on_subscribe()
def subscribe(client, mid, qos, properties):
    print('subscribed', client, mid, qos, properties)