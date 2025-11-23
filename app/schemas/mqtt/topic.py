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
from app.domain.repository_registry_model import RepositoryRegistry
from app.domain.unit_model import Unit
from app.dto.agent.abc import AgentBackend
from app.dto.clickhouse.log import UnitLog
from app.dto.enum import (
    DestinationTopicType,
    GlobalPrefixTopic,
    ReservedOutputBaseTopic,
    ReservedStateKey,
    UnitFirmwareUpdateStatus,
)
from app.repositories.git_repo_repository import GitRepoRepository
from app.repositories.repo_repository import RepoRepository
from app.repositories.repository_registry_repository import (
    RepositoryRegistryRepository,
)
from app.repositories.unit_log_repository import UnitLogRepository
from app.repositories.unit_repository import UnitRepository
from app.schemas.mqtt.utils import get_only_reserved_keys, get_topic_split
from app.services.validators import (
    is_valid_json,
    is_valid_object,
    is_valid_uuid,
)
from app.utils.utils import ensure_timezone_aware

mqtt_config = MQTTConfig(
    host=settings.pu_mqtt_host,
    port=settings.pu_mqtt_port,
    keepalive=settings.pu_mqtt_keepalive,
    username=AgentBackend(name=settings.pu_domain).generate_agent_token(),
    password="",
)

mqtt = FastMQTT(config=mqtt_config)

cache_dict = {}


@mqtt.on_connect()
def connect(client, _flags, _rc, _properties):
    lock_fd = acquire_file_lock("tmp/mqtt_subscribe.lock")

    time.sleep(2)

    if lock_fd:
        logging.info("MQTT subscriptions initialized in this worker")
        client.subscribe(
            f"{settings.pu_domain}/+/+/+{GlobalPrefixTopic.BACKEND_SUB_PREFIX.value}"
        )
    else:
        logging.info("Another worker already subscribed to MQTT topics")

    if lock_fd:
        lock_fd.close()


@mqtt.on_message()
async def message_to_topic(_client, topic, payload, _qos, _properties):
    topic_split = get_topic_split(topic)
    backend_domain, destination, unit_uuid, topic_name, *_ = topic_split
    unit_uuid = is_valid_uuid(unit_uuid)

    payload_size = len(payload.decode())
    if payload_size > settings.pu_mqtt_max_payload_size * 1024:
        msg = f"Payload size is {payload_size}, limit is {settings.pu_mqtt_max_payload_size} KB"
        raise MqttError(msg)

    if destination == DestinationTopicType.OUTPUT_BASE_TOPIC:
        if topic_name == ReservedOutputBaseTopic.STATE:
            last_time = cache_dict.get(topic, 0)
            current_time = time.time()

            if (current_time - last_time) < settings.pu_state_send_interval:
                if settings.pu_debug:
                    msg = f"Exceeding the message sending rate for the {topic} topic, you need to send values no more often than {settings.pu_state_send_interval}"
                    raise MqttError(msg)
                return

            cache_dict[topic] = current_time
            await _handle_state_message(unit_uuid, payload)
        elif topic_name == ReservedOutputBaseTopic.LOG:
            await _handle_log_message(unit_uuid, payload)


async def _handle_state_message(unit_uuid, payload):
    with get_hand_session() as db:
        unit_repository = UnitRepository(db)
        unit_state_dict = get_only_reserved_keys(
            is_valid_json(payload.decode(), "Hardware state")
        )

        unit = unit_repository.get(Unit(uuid=unit_uuid))
        is_valid_object(unit)

        unit.unit_state_dict = json.dumps(unit_state_dict)

        if (
            ReservedStateKey.PU_COMMIT_VERSION.value
            not in unit.unit_state_dict
        ):
            msg = "State dict has no pu_commit_version key"
            raise MqttError(msg)

        unit.current_commit_version = unit_state_dict[
            ReservedStateKey.PU_COMMIT_VERSION.value
        ]

        if (
            unit.firmware_update_status
            == UnitFirmwareUpdateStatus.REQUEST_SENT
        ):
            current_datetime = datetime.datetime.now(datetime.UTC)

            repo_repository = RepoRepository(db)
            repo = repo_repository.get(Repo(uuid=unit.repo_uuid))

            repository_registry_repository = RepositoryRegistryRepository(db)
            repository_registry = repository_registry_repository.get(
                RepositoryRegistry(uuid=repo.repository_registry_uuid)
            )

            git_repo_repository = GitRepoRepository()
            target_commit, target_tag = (
                git_repo_repository.get_target_unit_version(
                    repo, repository_registry, unit
                )
            )

            last_update_datetime = ensure_timezone_aware(
                unit.last_firmware_update_datetime
            )

            delta = (current_datetime - last_update_datetime).total_seconds()
            if target_commit == unit.current_commit_version:
                unit.firmware_update_error = None
                unit.last_firmware_update_datetime = None
                unit.firmware_update_status = UnitFirmwareUpdateStatus.SUCCESS

            elif delta > settings.pu_state_send_interval * 2:
                try:
                    msg = f"Device firmware update time is twice as fast as {settings.pu_state_send_interval}s times"
                    raise UpdateError(msg)
                except UpdateError as e:
                    unit.firmware_update_error = e.message

                unit.last_firmware_update_datetime = None
                unit.firmware_update_status = UnitFirmwareUpdateStatus.ERROR

        unit.last_update_datetime = datetime.datetime.now(datetime.UTC)
        unit_repository.update(
            unit_uuid,
            unit,
        )


async def _handle_log_message(unit_uuid, payload):
    with get_hand_clickhouse_client() as cc, get_hand_session() as db:
        try:
            unit_repository = UnitRepository(db)
            unit_log_repository = UnitLogRepository(cc)

            log_data = is_valid_json(payload.decode(), "Unit hardware log")

            unit = unit_repository.get(Unit(uuid=unit_uuid))
            is_valid_object(unit)

            if isinstance(log_data, dict):
                log_data = [log_data]

            server_datetime = datetime.datetime.now(datetime.UTC)

            unit_log_repository.bulk_create(
                [
                    UnitLog(
                        uuid=uuid.uuid4(),
                        level=item["level"].capitalize(),
                        unit_uuid=unit.uuid,
                        text=item["text"],
                        create_datetime=(
                            item["create_datetime"]
                            if item.get("create_datetime")
                            else server_datetime
                            + datetime.timedelta(seconds=inc)
                        ),
                        expiration_datetime=datetime.datetime.now(datetime.UTC)
                        + datetime.timedelta(
                            seconds=settings.pu_unit_log_expiration
                        ),
                    )
                    for inc, item in enumerate(log_data)
                ]
            )

            unit.last_update_datetime = datetime.datetime.now(datetime.UTC)
            unit_repository.update(
                unit_uuid,
                unit,
            )

        except Exception as e:
            logging.error(e)


@mqtt.on_disconnect()
def disconnect(client, _packet):
    logging.info(
        f"Disconnected from MQTT server: {settings.pu_mqtt_host}:{settings.pu_mqtt_port}"
    )

    async def reconnect():
        await asyncio.sleep(5)
        try:
            await client.reconnect()
        except Exception as e:
            logging.error(f"Reconnect failed: {e}")

    asyncio.create_task(reconnect())
