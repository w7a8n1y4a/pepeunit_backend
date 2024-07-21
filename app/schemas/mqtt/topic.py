import json
import time

from aiokeydb import KeyDBClient
from fastapi_mqtt import FastMQTT, MQTTConfig

from app import settings
from app.configs.db import get_session
from app.domain.unit_model import Unit
from app.repositories.enum import ReservedOutputBaseTopic, GlobalPrefixTopic, SchemaStructName
from app.repositories.permission_repository import PermissionRepository
from app.repositories.unit_node_repository import UnitNodeRepository
from app.repositories.unit_repository import UnitRepository
from app.repositories.user_repository import UserRepository
from app.schemas.mqtt.utils import get_topic_split
from app.services.access_service import AccessService
from app.services.unit_node_service import UnitNodeService
from app.services.utils import merge_two_dict_first_priority
from app.services.validators import is_valid_uuid

mqtt_config = MQTTConfig(
    host=settings.mqtt_host,
    port=settings.mqtt_port,
    keepalive=settings.mqtt_keepalive,
    username=AccessService.generate_current_instance_token(),
    password='',
)

mqtt = FastMQTT(config=mqtt_config)


@mqtt.on_connect()
def connect(client, flags, rc, properties):
    # Subscribe to a pattern
    print('connect')


KeyDBClient.init_session(uri=settings.redis_url)


@mqtt.subscribe(f'{settings.backend_domain}/+/pepeunit')
async def message_to_topic(client, topic, payload, qos, properties):
    backend_domain, unit_node_uuid, *_ = get_topic_split(topic)
    is_valid_uuid(unit_node_uuid)

    new_value = str(payload.decode())

    await KeyDBClient.async_wait_for_ready()
    redis_topic_value = await KeyDBClient.async_get(unit_node_uuid)

    if redis_topic_value != new_value:
        await KeyDBClient.async_set(unit_node_uuid, new_value)

        db = next(get_session())
        unit_node_service = UnitNodeService(
            unit_node_repository=UnitNodeRepository(db),
            access_service=AccessService(
                permission_repository=PermissionRepository(db),
                unit_repository=UnitRepository(db),
                user_repository=UserRepository(db),
            ),
        )
        unit_node_service.set_state(unit_node_uuid, str(payload.decode()))
        db.close()


@mqtt.subscribe(f'{settings.backend_domain}/+/+/+/pepeunit')
async def message_to_topic(client, topic, payload, qos, properties):
    backend_domain, destination, unit_uuid, topic_name, *_ = get_topic_split(topic)
    is_valid_uuid(unit_uuid)

    topic_name += GlobalPrefixTopic.BACKEND_SUB_PREFIX

    if destination == SchemaStructName.OUTPUT_BASE_TOPIC:
        if topic_name == ReservedOutputBaseTopic.STATE + GlobalPrefixTopic.BACKEND_SUB_PREFIX:
            db = next(get_session())
            unit_repository = UnitRepository(db)

            unit_state_dict = json.loads(payload.decode())

            current_unit = unit_repository.get(Unit(uuid=unit_uuid))

            new_unit_state = Unit(
                **merge_two_dict_first_priority(
                    {
                        'unit_state_dict': str(payload.decode()),
                        'current_commit_version': unit_state_dict['commit_version'],
                    },
                    current_unit.dict(),
                )
            )

            unit_repository.update(
                unit_uuid,
                new_unit_state,
            )
            db.close()


@mqtt.on_disconnect()
def disconnect(client, packet, exc=None):
    print("Disconnect", client._username)
