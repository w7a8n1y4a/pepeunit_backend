import time

from fastapi_mqtt import FastMQTT, MQTTConfig

from app import settings
from app.configs.db import get_session
from app.domain.test_model import Test

mqtt_config = MQTTConfig(
    host=settings.mqtt_host,
    port=settings.mqtt_port,
    keepalive=settings.mqtt_keepalive,
    username=settings.mqtt_username,
    password=settings.mqtt_password,
)

mqtt = FastMQTT(config=mqtt_config)

@mqtt.on_connect()
def connect(client, flags, rc, properties):
    mqtt.client.subscribe('test/#')  # subscribing mqtt topic
    print('Connected: ', client, flags, rc, properties)


# todo разделить на input и output
# cписок подписок на устройстве должен обновляться

@mqtt.subscribe('test/#')
async def message_to_topic(client, topic, payload, qos, properties):

    # todo аналог кэша через redis, чтобы можно было не обращаться к бд постоянно

    db = next(get_session())

    test = Test(value=f'{str(topic)}, {str(payload.decode())}')
    test.uuid = '7af0cb07-a0d0-41a8-81e9-251457e1a9d0'

    db.merge(test)

    start_time = time.perf_counter()
    db.commit()
    print(f'{time.perf_counter() - start_time}')

@mqtt.on_disconnect()
def disconnect(client, packet, exc=None):
    print('Disconnected')


@mqtt.on_subscribe()
def subscribe(client, mid, qos, properties):
    print('subscribed', client, mid, qos, properties)