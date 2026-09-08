import datetime
import json
import logging
import time
import uuid

from app import BackendLogLevel, settings
from app.configs.clickhouse import get_hand_clickhouse_client
from app.configs.db import get_hand_session
from app.configs.errors import MqttError
from app.domain.repo_model import Repo
from app.domain.repository_registry_model import RepositoryRegistry
from app.domain.unit_model import Unit
from app.dto.clickhouse.log import UnitLog
from app.dto.enum import (
    DestinationTopicType,
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


class MqttMessageHandler:
    def __init__(self) -> None:
        self.last_state_times: dict[str, float] = {}

    async def handle(self, topic: str, payload: bytes) -> None:
        payload_size = len(payload.decode())
        if payload_size > settings.pu_mqtt_max_payload_size * 1024:
            msg = (
                f"Payload size is {payload_size}, "
                f"limit is {settings.pu_mqtt_max_payload_size} KB"
            )
            raise MqttError(msg)

        backend_domain, destination, unit_uuid, topic_name, *_ = (
            get_topic_split(topic)
        )
        if destination != DestinationTopicType.OUTPUT_BASE_TOPIC:
            return
        if backend_domain != settings.pu_domain:
            msg = (
                f"Topic domain {backend_domain} is invalid, "
                f"expected {settings.pu_domain}"
            )
            raise MqttError(msg)

        unit_uuid = is_valid_uuid(unit_uuid)

        if topic_name == ReservedOutputBaseTopic.STATE:
            await self.handle_state(topic, unit_uuid, payload)
        elif topic_name == ReservedOutputBaseTopic.LOG:
            await self.handle_log(unit_uuid, payload)

    async def handle_state(
        self, topic: str, unit_uuid, payload: bytes
    ) -> None:
        with get_hand_session() as db:
            unit_repository = UnitRepository(db)
            unit_state_dict = get_only_reserved_keys(
                is_valid_json(payload.decode(), "Hardware state")
            )

            unit = unit_repository.get(Unit(uuid=unit_uuid))
            is_valid_object(unit)

            new_commit = self._get_commit_version(unit_state_dict)
            waiting_firmware = (
                unit.firmware_update_status
                == UnitFirmwareUpdateStatus.REQUEST_SENT
            )
            same_commit = new_commit == unit.current_commit_version
            too_frequent = self._is_state_rate_limited(topic)

            if same_commit and not waiting_firmware and too_frequent:
                self._reject_rate_limited_state(topic)
                return

            self.last_state_times[topic] = time.time()
            unit.unit_state_dict = json.dumps(unit_state_dict)
            unit.current_commit_version = new_commit
            unit.last_update_datetime = datetime.datetime.now(datetime.UTC)

            self._sync_firmware_update_status(db, unit)
            unit_repository.update(unit_uuid, unit)

    async def handle_log(self, unit_uuid, payload: bytes) -> None:
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
                            expiration_datetime=datetime.datetime.now(
                                datetime.UTC
                            )
                            + datetime.timedelta(
                                seconds=settings.pu_unit_log_expiration
                            ),
                        )
                        for inc, item in enumerate(log_data)
                    ]
                )

                unit.last_update_datetime = datetime.datetime.now(datetime.UTC)
                unit_repository.update(unit_uuid, unit)

            except Exception as e:
                logging.error(e)

    def _is_state_rate_limited(self, topic: str) -> bool:
        last_time = self.last_state_times.get(topic, 0)
        return time.time() - last_time < settings.pu_state_send_interval

    @staticmethod
    def _get_commit_version(unit_state_dict: dict) -> str:
        commit = unit_state_dict.get(ReservedStateKey.PU_COMMIT_VERSION.value)
        if not commit:
            msg = "State dict has no pu_commit_version key"
            raise MqttError(msg)
        return commit

    @staticmethod
    def _reject_rate_limited_state(topic: str) -> None:
        if settings.pu_min_log_level != BackendLogLevel.DEBUG:
            return

        msg = (
            f"Exceeding the message sending rate for the {topic} topic, "
            f"you need to send values no more often than "
            f"{settings.pu_state_send_interval}"
        )
        raise MqttError(msg)

    @staticmethod
    def _sync_firmware_update_status(db, unit: Unit) -> None:
        if (
            unit.firmware_update_status
            != UnitFirmwareUpdateStatus.REQUEST_SENT
        ):
            return

        repo = RepoRepository(db).get(Repo(uuid=unit.repo_uuid))
        repository_registry = RepositoryRegistryRepository(db).get(
            RepositoryRegistry(uuid=repo.repository_registry_uuid)
        )
        target_commit, _ = GitRepoRepository().get_target_unit_version(
            repo, repository_registry, unit
        )

        elapsed = (
            datetime.datetime.now(datetime.UTC)
            - ensure_timezone_aware(unit.last_firmware_update_datetime)
        ).total_seconds()

        if target_commit == unit.current_commit_version:
            unit.firmware_update_error = None
            unit.last_firmware_update_datetime = None
            unit.firmware_update_status = UnitFirmwareUpdateStatus.SUCCESS
            return

        if elapsed <= settings.pu_state_send_interval * 2:
            return

        unit.firmware_update_error = (
            f"Device firmware update time is twice as fast as "
            f"{settings.pu_state_send_interval}s times"
        )
        unit.last_firmware_update_datetime = None
        unit.firmware_update_status = UnitFirmwareUpdateStatus.ERROR
