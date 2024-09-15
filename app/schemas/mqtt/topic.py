import json
import logging

from aiokeydb import KeyDBClient
from fastapi_mqtt import FastMQTT, MQTTConfig

from app import settings
from app.configs.db import get_session
from app.configs.gql import get_unit_node_service
from app.configs.sub_entities import InfoSubEntity
from app.domain.unit_model import Unit
from app.repositories.enum import DestinationTopicType, GlobalPrefixTopic, ReservedOutputBaseTopic
from app.repositories.unit_repository import UnitRepository
from app.schemas.mqtt.utils import get_topic_split
from app.services.utils import merge_two_dict_first_priority
from app.services.validators import is_valid_uuid

mqtt_config = MQTTConfig(
    host=settings.mqtt_host,
    port=settings.mqtt_port,
    keepalive=settings.mqtt_keepalive,
    username=settings.backend_token,
    password='',
)

mqtt = FastMQTT(config=mqtt_config)

KeyDBClient.init_session(uri=settings.redis_url)


@mqtt.on_message()
async def message_to_topic(client, topic, payload, qos, properties):

    topic_split = get_topic_split(topic)

    if len(topic_split) == 5:
        backend_domain, destination, unit_uuid, topic_name, *_ = topic_split
        unit_uuid = is_valid_uuid(unit_uuid)

        topic_name += GlobalPrefixTopic.BACKEND_SUB_PREFIX

        if destination == DestinationTopicType.OUTPUT_BASE_TOPIC:
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

    elif len(topic_split) == 3:
        backend_domain, unit_node_uuid, *_ = topic_split
        unit_node_uuid = is_valid_uuid(unit_node_uuid)

        new_value = str(payload.decode())

        await KeyDBClient.async_wait_for_ready()
        redis_topic_value = await KeyDBClient.async_get(str(unit_node_uuid))

        if redis_topic_value != new_value:
            await KeyDBClient.async_set(str(unit_node_uuid), new_value)

            db = next(get_session())
            unit_node_service = get_unit_node_service(InfoSubEntity({'db': db, 'jwt_token': None}))
            unit_node_service.set_state(unit_node_uuid, str(payload.decode()))
            db.close()
    else:
        pass


@mqtt.on_disconnect()
def disconnect(client, packet, exc=None):
    logging.info(f'Disconnect mqtt server: {settings.mqtt_host}:{settings.mqtt_port}')
