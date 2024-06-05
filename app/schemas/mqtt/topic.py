import json
import time

from aiokeydb import KeyDBClient
from fastapi_mqtt import FastMQTT, MQTTConfig

from app import settings
from app.configs.db import get_session
from app.domain.unit_model import Unit
from app.repositories.enum import ReservedOutputBaseTopic
from app.repositories.permission_repository import PermissionRepository
from app.repositories.unit_node_repository import UnitNodeRepository
from app.repositories.unit_repository import UnitRepository
from app.repositories.user_repository import UserRepository
from app.schemas.mqtt.utils import get_topic_split
from app.services.access_service import AccessService
from app.services.unit_node_service import UnitNodeService

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
    # Subscribe to a pattern
    print('connect')

    mqtt.client.subscribe(f'{settings.backend_domain}/+/+/+/pepeunit')

KeyDBClient.init_session(uri=settings.redis_url)

@mqtt.on_message()
async def message_to_topic(client, topic, payload, qos, properties):
    start = time.perf_counter()
    backend_domain, destination, unit_uuid, topic_name, *_ = get_topic_split(topic)

    topic_name += '/pepeunit'

    if destination in ['input', 'output']:

        _, count_dec, count = payload.decode().split(' ')

        count_dec = int(count_dec)
        count = int(count)

        await KeyDBClient.async_wait_for_ready()

        redis_topic_value = await KeyDBClient.async_get(topic_name)

        if redis_topic_value != str(count_dec):
            await KeyDBClient.async_set(topic_name, str(count_dec))

            # db = next(get_session())
            # unit_node_service = UnitNodeService(
            #     unit_node_repository=UnitNodeRepository(db),
            #     access_service=AccessService(
            #         permission_repository=PermissionRepository(db),
            #         unit_repository=UnitRepository(db),
            #         user_repository=UserRepository(db),
            #     ),
            # )
            # unit_node_service.set_state(unit_uuid, topic_name, destination.capitalize(), str(payload.decode()))
            # db.close()

        if count % 100 == 0:
            print(f'{str(payload.decode())}')
            print(time.perf_counter() - start)

        await KeyDBClient.aclose()


    elif destination == 'output_base':
        if topic_name == ReservedOutputBaseTopic.STATE + '/pepeunit':
            db = next(get_session())
            unit_repository = UnitRepository(db)

            unit_state_dict = json.loads(payload.decode())

            unit_repository.update(
                unit_uuid,
                Unit(unit_state_dict=str(payload.decode()), current_commit_version=unit_state_dict['commit_version']),
            )
            db.close()


@mqtt.on_disconnect()
def disconnect(client, packet, exc=None):
    print("Disconnect", client._username)
