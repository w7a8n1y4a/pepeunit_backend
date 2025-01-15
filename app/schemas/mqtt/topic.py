import datetime
import json
import logging

from aiokeydb import KeyDBClient
from fastapi_mqtt import FastMQTT, MQTTConfig

from app import settings
from app.configs.db import get_session
from app.configs.errors import app_errors
from app.configs.gql import get_unit_node_service
from app.configs.sub_entities import InfoSubEntity
from app.domain.repo_model import Repo
from app.domain.unit_model import Unit
from app.repositories.enum import (
    DestinationTopicType,
    GlobalPrefixTopic,
    ReservedOutputBaseTopic,
    UnitFirmwareUpdateStatus,
)
from app.repositories.git_repo_repository import GitRepoRepository
from app.repositories.repo_repository import RepoRepository
from app.repositories.unit_repository import UnitRepository
from app.schemas.mqtt.utils import get_only_reserved_keys, get_topic_split
from app.services.validators import is_valid_json, is_valid_object, is_valid_uuid

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
                try:
                    unit_repository = UnitRepository(db)

                    unit_state_dict = get_only_reserved_keys(is_valid_json(payload.decode(), "hardware state"))

                    unit = unit_repository.get(Unit(uuid=unit_uuid))
                    is_valid_object(unit)

                    unit.unit_state_dict = json.dumps(unit_state_dict)

                    if not 'commit_version':
                        app_errors.mqtt_error.raise_exception('State dict has no commit_version key')

                    unit.current_commit_version = unit_state_dict['commit_version']

                    if unit.firmware_update_status == UnitFirmwareUpdateStatus.REQUEST_SENT:
                        current_datetime = datetime.datetime.utcnow()

                        repo_repository = RepoRepository(db)
                        repo = repo_repository.get(Repo(uuid=unit.repo_uuid))

                        git_repo_repository = GitRepoRepository()
                        target_commit, target_tag = git_repo_repository.get_target_unit_version(repo, unit)

                        delta = (current_datetime - unit.last_firmware_update_datetime).total_seconds()
                        if target_commit == unit.current_commit_version:
                            unit.firmware_update_error = None
                            unit.last_firmware_update_datetime = None
                            unit.firmware_update_status = UnitFirmwareUpdateStatus.SUCCESS

                        elif delta > settings.state_send_interval * 2:
                            try:
                                app_errors.update_error.raise_exception(
                                    'Device firmware update time is twice as fast as {}s times'.format(
                                        settings.state_send_interval
                                    )
                                )
                            except Exception as ex:
                                unit.firmware_update_error = ex.detail

                            unit.last_firmware_update_datetime = None
                            unit.firmware_update_status = UnitFirmwareUpdateStatus.ERROR

                    unit_repository.update(
                        unit_uuid,
                        unit,
                    )
                except Exception as ex:
                    logging.error(ex)
                finally:
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
            try:
                unit_node_service = get_unit_node_service(InfoSubEntity({'db': db, 'jwt_token': None}))
                unit_node_service.set_state(unit_node_uuid, str(payload.decode()))
            except Exception as ex:
                logging.error(ex)
            finally:
                db.close()
    else:
        pass


@mqtt.on_disconnect()
def disconnect(client, packet, exc=None):
    logging.info(f'Disconnect mqtt server: {settings.mqtt_host}:{settings.mqtt_port}')
