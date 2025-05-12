import asyncio
import datetime
import json
import logging
import time
import uuid

from fastapi_mqtt import FastMQTT, MQTTConfig

from app import settings
from app.configs.clickhouse import get_hand_clickhouse_client
from app.configs.db import get_hand_session
from app.configs.errors import MqttError, UpdateError
from app.configs.utils import acquire_file_lock
from app.domain.repo_model import Repo
from app.domain.unit_model import Unit
from app.dto.agent.abc import AgentBackend
from app.dto.clickhouse.log import UnitLog
from app.dto.enum import (
    DestinationTopicType,
    GlobalPrefixTopic,
    ReservedOutputBaseTopic,
    UnitFirmwareUpdateStatus,
)
from app.repositories.git_repo_repository import GitRepoRepository
from app.repositories.repo_repository import RepoRepository
from app.repositories.unit_log_repository import UnitLogRepository
from app.repositories.unit_repository import UnitRepository
from app.schemas.mqtt.utils import get_only_reserved_keys, get_topic_split
from app.services.validators import is_valid_json, is_valid_object, is_valid_uuid

mqtt_config = MQTTConfig(
    host=settings.mqtt_host,
    port=settings.mqtt_port,
    keepalive=settings.mqtt_keepalive,
    username=AgentBackend(name=settings.backend_domain).generate_agent_token(),
    password='',
)

mqtt = FastMQTT(config=mqtt_config)

cache_dict = {}


@mqtt.on_connect()
def connect(client, flags, rc, properties):
    lock_fd = acquire_file_lock('tmp/mqtt_subscribe.lock')

    time.sleep(2)

    if lock_fd:
        logging.info("MQTT subscriptions initialized in this worker")
        client.subscribe(f'{settings.backend_domain}/+/+/+{GlobalPrefixTopic.BACKEND_SUB_PREFIX}')
    else:
        logging.info("Another worker already subscribed to MQTT topics")

    if lock_fd:
        lock_fd.close()


@mqtt.on_message()
async def message_to_topic(client, topic, payload, qos, properties):

    topic_split = get_topic_split(topic)
    backend_domain, destination, unit_uuid, topic_name, *_ = topic_split
    unit_uuid = is_valid_uuid(unit_uuid)

    last_time = cache_dict.get(str(unit_uuid), 0)
    current_time = time.time()

    if (current_time - last_time) < settings.backend_state_send_interval:
        raise MqttError(
            'Exceeding the message sending rate for the {} topic, you need to send values no more often than {}'.format(
                topic, settings.mqtt_max_payload_size
            )
        )

    cache_dict[str(unit_uuid)] = current_time

    payload_size = len(payload.decode())
    if payload_size > settings.mqtt_max_payload_size * 1024:
        raise MqttError('Payload size is {}, limit is {} KB'.format(payload_size, settings.mqtt_max_payload_size))

    if destination == DestinationTopicType.OUTPUT_BASE_TOPIC and topic_name == ReservedOutputBaseTopic.STATE:
        with get_hand_session() as db:
            unit_repository = UnitRepository(db)
            unit_state_dict = get_only_reserved_keys(is_valid_json(payload.decode(), "hardware state"))

            unit = unit_repository.get(Unit(uuid=unit_uuid))
            is_valid_object(unit)

            unit.unit_state_dict = json.dumps(unit_state_dict)

            if not 'commit_version' in unit.unit_state_dict:
                raise MqttError('State dict has no commit_version key')

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

                elif delta > settings.backend_state_send_interval * 2:
                    try:
                        raise UpdateError(
                            'Device firmware update time is twice as fast as {}s times'.format(
                                settings.backend_state_send_interval
                            )
                        )
                    except UpdateError as e:
                        unit.firmware_update_error = e.message

                    unit.last_firmware_update_datetime = None
                    unit.firmware_update_status = UnitFirmwareUpdateStatus.ERROR

            unit.last_update_datetime = datetime.datetime.utcnow()
            unit_repository.update(
                unit_uuid,
                unit,
            )

    elif destination == DestinationTopicType.OUTPUT_BASE_TOPIC and topic_name == ReservedOutputBaseTopic.LOG:
        with get_hand_clickhouse_client() as cc:
            with get_hand_session() as db:
                try:
                    unit_repository = UnitRepository(db)
                    unit_log_repository = UnitLogRepository(cc)

                    log_data = is_valid_json(payload.decode(), "unit hardware log")

                    unit = unit_repository.get(Unit(uuid=unit_uuid))
                    is_valid_object(unit)

                    if isinstance(log_data, dict):
                        log_data = [log_data]

                    server_datetime = datetime.datetime.utcnow()

                    unit_log_repository.bulk_create(
                        [
                            UnitLog(
                                uuid=uuid.uuid4(),
                                level=item['level'].capitalize(),
                                unit_uuid=unit.uuid,
                                text=item['text'],
                                create_datetime=(
                                    item['create_datetime']
                                    if item.get('create_datetime')
                                    else server_datetime + datetime.timedelta(seconds=inc)
                                ),
                                expiration_datetime=datetime.datetime.utcnow()
                                + datetime.timedelta(seconds=settings.backend_unit_log_expiration),
                            )
                            for inc, item in enumerate(log_data)
                        ]
                    )

                    unit.last_update_datetime = datetime.datetime.utcnow()
                    unit_repository.update(
                        unit_uuid,
                        unit,
                    )

                except Exception as e:
                    logging.error(e)
    else:
        pass


@mqtt.on_disconnect()
def disconnect(client, packet, exc=None):
    logging.info(f'Disconnected from MQTT server: {settings.mqtt_host}:{settings.mqtt_port}')

    async def reconnect():
        await asyncio.sleep(5)
        try:
            await client.reconnect()
        except Exception as e:
            logging.error(f"Reconnect failed: {e}")

    asyncio.create_task(reconnect())
