import base64
import builtins
import contextlib
import copy
import datetime
import itertools
import json
import logging
import os
import shutil
import uuid as uuid_pkg
import zlib

from fastapi import Depends

from app import runtime, settings
from app.configs.error_codes import ErrorCode
from app.configs.errors import MqttError, NoAccessError, UnitError
from app.domain.operation_task_model import OperationTask
from app.domain.repo_model import Repo
from app.domain.unit_io_model import UnitIO
from app.domain.unit_model import Unit
from app.domain.user_model import User
from app.dto.agent.abc import AgentBackend, AgentUnit
from app.dto.clickhouse.log import UnitLog
from app.dto.enum import (
    AgentType,
    BackendTopicCommand,
    DestinationTopicType,
    JsonPayload,
    LogLevel,
    NotFoundEntity,
    OperationTaskType,
    OrderByDate,
    OwnershipType,
    PermissionEntities,
    ReservedEnvVariableName,
    StaticRepoFileName,
    UnitIOTypeEnum,
    UserRole,
    UuidEntity,
)
from app.repositories.git_repo_repository import GitRepoRepository
from app.repositories.icon_repository import IconRepository
from app.repositories.repo_repository import (
    RepoRepository,
)
from app.repositories.unit_io_repository import UnitIORepository
from app.repositories.unit_log_repository import UnitLogRepository
from app.repositories.unit_repository import UnitRepository
from app.schemas.mqtt.utils import get_topic_split
from app.schemas.pydantic.operation_task import OperationTaskCreate
from app.schemas.pydantic.shared import UnitIORead
from app.schemas.pydantic.unit import (
    TargetVersionRead,
    UnitCreate,
    UnitFilter,
    UnitLogFilter,
    UnitRead,
    UnitUpdate,
)
from app.schemas.pydantic.unit_io import UnitIOFilter
from app.services.access_service import AccessService
from app.services.background import BackgroundService
from app.services.icon_image import IconImage
from app.services.operation_task_service import OperationTaskService
from app.services.permission_service import PermissionService
from app.services.unit_io_service import UnitIOService
from app.services.utils import (
    get_topic_name,
    merge_two_dict_first_priority,
    remove_none_value_dict,
    toml_file_to_md,
)
from app.services.validators import (
    is_valid_json,
    is_valid_object,
    is_valid_uuid,
)
from app.utils.utils import aes_gcm_decode, aes_gcm_encode


class UnitService:
    def __init__(
        self,
        unit_repository: UnitRepository = Depends(),
        icon_repository: IconRepository = Depends(),
        repo_repository: RepoRepository = Depends(),
        unit_io_repository: UnitIORepository = Depends(),
        unit_log_repository: UnitLogRepository = Depends(),
        access_service: AccessService = Depends(),
        permission_service: PermissionService = Depends(),
        operation_task_service: OperationTaskService = Depends(),
        unit_io_service: UnitIOService = Depends(),
    ) -> None:
        self.unit_repository = unit_repository
        self.icon_repository = icon_repository
        self.repo_repository = repo_repository
        self.git_repo_repository = GitRepoRepository()
        self.unit_io_repository = unit_io_repository
        self.unit_log_repository = unit_log_repository
        self.access_service = access_service
        self.permission_service = permission_service
        self.operation_task_service = operation_task_service
        self.unit_io_service = unit_io_service

    def create(self, data: UnitCreate) -> Unit:
        self.access_service.authorization.check_access([AgentType.USER])
        self.unit_repository.is_valid_name(data.name)

        repo = self.repo_repository.get(Repo(uuid=data.repo_uuid))
        is_valid_object(repo, NotFoundEntity.REPO)
        self.access_service.authorization.check_repo_access(repo)

        unit = Unit(
            creator_uuid=self.access_service.current_agent.uuid, **data.dict()
        )
        self.is_valid_update_rule(unit)
        target_commit, target_tag = (
            self.git_repo_repository.get_target_unit_version(repo, unit)
        )
        self.git_repo_repository.is_valid_firmware_platform(
            repo,
            unit,
            unit.target_firmware_platform,
            (target_commit, target_tag),
        )
        self.git_repo_repository.is_valid_schema_file(repo, target_commit)
        if not unit.is_auto_update_unit:
            self.git_repo_repository.get_env_dict(repo, target_commit)

        schema_dict = self.git_repo_repository.get_schema_dict(
            repo, target_commit
        )

        unit.create_datetime = datetime.datetime.now(datetime.UTC)
        unit.last_update_datetime = unit.create_datetime
        unit.icon_uuid = self.icon_repository.stage(
            IconImage.generate(str(unit.uuid))
        ).uuid
        unit = self.unit_repository.create(unit)
        unit_deepcopy = copy.deepcopy(unit)

        self.permission_service.create_by_domains(
            User(uuid=self.access_service.current_agent.uuid), unit
        )
        self.permission_service.create_by_domains(unit, unit)

        self.unit_io_service.bulk_create(schema_dict, unit, False)

        return unit_deepcopy

    def get(self, uuid: uuid_pkg.UUID) -> Unit:
        self.access_service.authorization.check_access(
            [AgentType.BOT, AgentType.USER, AgentType.UNIT]
        )
        unit = self.unit_repository.get(Unit(uuid=uuid))
        is_valid_object(unit, NotFoundEntity.UNIT)
        self.access_service.authorization.check_visibility(unit)
        return unit

    def update(self, uuid: uuid_pkg.UUID, data: UnitUpdate) -> Unit:
        self.access_service.authorization.check_access([AgentType.USER])

        unit = self.unit_repository.get(Unit(uuid=uuid))
        is_valid_object(unit, NotFoundEntity.UNIT)
        self.access_service.authorization.check_ownership(
            unit, [OwnershipType.CREATOR]
        )

        unit_update = Unit(
            **merge_two_dict_first_priority(
                remove_none_value_dict(data.dict()), unit.dict()
            )
        )
        self.unit_repository.is_valid_name(unit_update.name)

        repo = self.repo_repository.get(Repo(uuid=unit.repo_uuid))
        is_valid_object(repo, NotFoundEntity.REPO)
        self.is_valid_update_rule(unit_update)
        target_commit, target_tag = (
            self.git_repo_repository.get_target_unit_version(repo, unit_update)
        )
        self.git_repo_repository.is_valid_firmware_platform(
            repo,
            unit_update,
            unit_update.target_firmware_platform,
            (target_commit, target_tag),
        )

        unit_update.last_update_datetime = datetime.datetime.now(datetime.UTC)
        result_unit = self.unit_repository.update(uuid, unit_update)
        self.unit_io_service.bulk_set_visibility_level(result_unit)

        result_unit = self.sync_state_unit_ios_for_version(
            result_unit, repo, (target_commit, target_tag)
        )
        with contextlib.suppress(MqttError):
            self.unit_io_service.command_to_input_base_topic(
                uuid=result_unit.uuid,
                command=BackendTopicCommand.UPDATE,
                is_auto_update=True,
            )

        return result_unit

    def sync_state_unit_ios_for_version(
        self,
        unit: Unit,
        repo: Repo,
        target_version_with_tag: tuple[str, str | None] = None,
    ) -> Unit:
        target_version, target_tag = (
            target_version_with_tag
            or self.git_repo_repository.get_target_unit_version(repo, unit)
        )
        self.git_repo_repository.is_valid_firmware_platform(
            repo,
            unit,
            unit.target_firmware_platform,
            target_version_with_tag=(target_version, target_tag),
        )

        if target_version == unit.current_commit_version:
            return self.unit_repository.update(unit.uuid, unit)

        self.git_repo_repository.is_valid_schema_file(repo, target_version)

        if unit.cipher_env_dict:
            new_env_dict = self.generate_unified_env(
                unit=unit,
                repo=repo,
                target_version=target_version,
                user_env_dict=None,
                include_commit_version=True,
                filter_by_allowed_keys=True,
            )

            self.git_repo_repository.is_valid_env_file(
                repo, target_version, new_env_dict
            )

            unit.cipher_env_dict = aes_gcm_encode(json.dumps(new_env_dict))

            unit = self.unit_repository.update(unit.uuid, unit)

        count, all_exist_unit_ios = self.unit_io_repository.list(
            UnitIOFilter.unlimited(unit_uuid=unit.uuid)
        )

        input_node_dict = {
            unit_io.topic_name: unit_io.uuid
            for unit_io in all_exist_unit_ios
            if unit_io.type == UnitIOTypeEnum.INPUT
        }

        output_node_dict = {
            unit_io.topic_name: unit_io.uuid
            for unit_io in all_exist_unit_ios
            if unit_io.type == UnitIOTypeEnum.OUTPUT
        }

        schema_dict = self.git_repo_repository.get_schema_dict(
            repo, target_version
        )

        self.unit_io_service.bulk_update(
            schema_dict, unit, input_node_dict, output_node_dict
        )

        unit.last_update_datetime = datetime.datetime.now(datetime.UTC)
        return self.unit_repository.update(unit.uuid, unit)

    def get_env(self, uuid: uuid_pkg.UUID) -> dict:
        self.access_service.authorization.check_access(
            [AgentType.USER, AgentType.UNIT]
        )

        unit = self.unit_repository.get(Unit(uuid=uuid))

        self.access_service.authorization.check_ownership(
            unit, [OwnershipType.CREATOR, OwnershipType.UNIT]
        )

        repo = self.repo_repository.get(Repo(uuid=unit.repo_uuid))
        is_valid_object(repo, NotFoundEntity.REPO)

        target_commit, target_tag = (
            self.git_repo_repository.get_target_unit_version(repo, unit)
        )

        return self.generate_unified_env(
            unit=unit,
            repo=repo,
            target_version=target_commit,
            user_env_dict=None,
            include_commit_version=True,
            filter_by_allowed_keys=True,
        )

    def set_env(self, uuid: uuid_pkg.UUID, env_json_str: str) -> None:
        self.access_service.authorization.check_access([AgentType.USER])

        unit = self.unit_repository.get(Unit(uuid=uuid))

        self.access_service.authorization.check_ownership(
            unit, [OwnershipType.CREATOR]
        )

        repo = self.repo_repository.get(Repo(uuid=unit.repo_uuid))
        is_valid_object(repo, NotFoundEntity.REPO)

        target_version = self.git_repo_repository.get_target_unit_version(
            repo, unit
        )[0]

        env_dict = self.generate_unified_env(
            unit=unit,
            repo=repo,
            target_version=target_version,
            user_env_dict=is_valid_json(env_json_str, JsonPayload.ENV),
            include_commit_version=False,
            filter_by_allowed_keys=True,
        )

        self.git_repo_repository.is_valid_env_file(
            repo, target_version, env_dict
        )

        unit.cipher_env_dict = aes_gcm_encode(json.dumps(env_dict))
        unit.last_update_datetime = datetime.datetime.now(datetime.UTC)
        self.unit_repository.update(unit.uuid, unit)

    def reset_env(self, uuid: uuid_pkg.UUID) -> None:
        self.access_service.authorization.check_access([AgentType.USER])

        unit = self.unit_repository.get(Unit(uuid=uuid))

        self.access_service.authorization.check_ownership(
            unit, [OwnershipType.CREATOR]
        )

        unit.cipher_env_dict = None
        unit.last_update_datetime = datetime.datetime.now(datetime.UTC)
        self.unit_repository.update(unit.uuid, unit)

    def get_target_version(self, uuid: uuid_pkg.UUID) -> TargetVersionRead:
        self.access_service.authorization.check_access(
            [AgentType.USER, AgentType.UNIT]
        )
        unit = self.unit_repository.get(Unit(uuid=uuid))
        is_valid_object(unit, NotFoundEntity.UNIT)

        self.access_service.authorization.check_ownership(
            unit, [OwnershipType.CREATOR, OwnershipType.UNIT]
        )

        repo = self.repo_repository.get(Repo(uuid=unit.repo_uuid))
        is_valid_object(repo, NotFoundEntity.REPO)

        target_commit, target_tag = (
            self.git_repo_repository.get_target_unit_version(repo, unit)
        )
        return TargetVersionRead(commit=target_commit, tag=target_tag)

    def get_current_schema(self, uuid: uuid_pkg.UUID) -> dict:
        self.access_service.authorization.check_access(
            [AgentType.USER, AgentType.UNIT]
        )
        unit = self.unit_repository.get(Unit(uuid=uuid))

        is_valid_object(unit, NotFoundEntity.UNIT)

        self.access_service.authorization.check_ownership(
            unit, [OwnershipType.CREATOR, OwnershipType.UNIT]
        )

        repo = self.repo_repository.get(Repo(uuid=unit.repo_uuid))
        is_valid_object(repo, NotFoundEntity.REPO)

        target_version = self.git_repo_repository.get_target_unit_version(
            repo, unit
        )[0]

        return self.generate_current_schema(unit, repo, target_version)

    def get_unit_firmware(self, uuid: uuid_pkg.UUID) -> str:
        self.access_service.authorization.check_access(
            [AgentType.USER, AgentType.UNIT]
        )

        unit = self.unit_repository.get(Unit(uuid=uuid))

        self.access_service.authorization.check_ownership(
            unit, [OwnershipType.CREATOR, OwnershipType.UNIT]
        )

        repo = self.repo_repository.get(Repo(uuid=unit.repo_uuid))
        is_valid_object(repo, NotFoundEntity.REPO)

        target_version = self.git_repo_repository.get_target_unit_version(
            repo, unit
        )[0]

        env_dict = self.get_env(unit.uuid)
        self.git_repo_repository.is_valid_env_file(
            repo, target_version, env_dict
        )

        gen_uuid = uuid_pkg.uuid4()

        if unit.is_compilable_unit:
            tmp_git_repo_path = self.git_repo_repository.get_tmp_path(gen_uuid)
            os.mkdir(tmp_git_repo_path)
        else:
            tmp_git_repo_path = self.git_repo_repository.generate_tmp_git_repo(
                repo, target_version, gen_uuid
            )

        env_dict[ReservedEnvVariableName.PU_COMMIT_VERSION.value] = (
            target_version
        )

        with open(
            f"{tmp_git_repo_path}/{StaticRepoFileName.ENV.value}", "w"
        ) as f:
            f.write(json.dumps(env_dict, indent=4))

        new_schema_dict = self.generate_current_schema(
            unit, repo, target_version
        )

        with open(
            f"{tmp_git_repo_path}/{StaticRepoFileName.SCHEMA.value}", "w"
        ) as f:
            f.write(json.dumps(new_schema_dict, indent=4))

        return tmp_git_repo_path

    def get_unit_firmware_zip(self, uuid: uuid_pkg.UUID) -> str:
        firmware_path = self.get_unit_firmware(uuid)
        firmware_zip_path = f"tmp/{uuid}"

        shutil.make_archive(firmware_zip_path, "zip", firmware_path)
        shutil.rmtree(firmware_path, ignore_errors=True)

        return f"{firmware_zip_path}.zip"

    def get_unit_firmware_tar(self, uuid: uuid_pkg.UUID) -> str:
        firmware_path = self.get_unit_firmware(uuid)
        firmware_tar_path = f"tmp/{uuid}"

        shutil.make_archive(firmware_tar_path, "tar", firmware_path)
        shutil.rmtree(firmware_path, ignore_errors=True)

        return f"{firmware_tar_path}.tar"

    def get_unit_firmware_tgz(
        self, uuid: uuid_pkg.UUID, wbits: int = 15, level: int = 9
    ) -> str:
        self.is_valid_wbits(wbits)
        self.is_valid_level(level)

        firmware_path = self.get_unit_firmware(uuid)
        firmware_tar_path = f"tmp/{uuid}"

        shutil.make_archive(firmware_tar_path, "tar", firmware_path)
        shutil.rmtree(firmware_path, ignore_errors=True)

        with open(firmware_tar_path + ".tar", "rb") as tar_file:
            producer = zlib.compressobj(wbits=wbits, level=level)

            tar_data = producer.compress(tar_file.read()) + producer.flush()

            with open(f"{firmware_tar_path}.tgz", "wb") as tgz:
                tgz.write(tar_data)

        os.remove(firmware_tar_path + ".tar")

        return f"{firmware_tar_path}.tgz"

    async def convert_toml_file_to_md(self, file) -> str:
        self.access_service.authorization.check_access([AgentType.USER])
        return await toml_file_to_md(file)

    def set_state_storage(self, uuid: uuid_pkg.UUID, state: str) -> None:
        self.access_service.authorization.check_access(
            [AgentType.USER, AgentType.UNIT]
        )
        unit = self.unit_repository.get(Unit(uuid=uuid))

        is_valid_object(unit, NotFoundEntity.UNIT)

        self.access_service.authorization.check_ownership(
            unit, [OwnershipType.CREATOR, OwnershipType.UNIT]
        )

        unit.cipher_state_storage = (
            aes_gcm_encode(state) if state != "" else None
        )
        unit.last_update_datetime = datetime.datetime.now(datetime.UTC)
        self.unit_repository.update(unit.uuid, unit)

    def get_state_storage(self, uuid: uuid_pkg.UUID) -> str:
        self.access_service.authorization.check_access(
            [AgentType.USER, AgentType.UNIT]
        )
        unit = self.unit_repository.get(Unit(uuid=uuid))

        is_valid_object(unit, NotFoundEntity.UNIT)

        self.access_service.authorization.check_ownership(
            unit, [OwnershipType.CREATOR, OwnershipType.UNIT]
        )

        return (
            aes_gcm_decode(unit.cipher_state_storage)
            if unit.cipher_state_storage
            else ""
        )

    def get_mqtt_auth(self, topic: str) -> None:
        self.access_service.authorization.check_access(
            [AgentType.BACKEND, AgentType.UNIT]
        )

        if isinstance(
            self.access_service.current_agent, AgentUnit | AgentBackend
        ):
            struct_topic = get_topic_split(topic)

            len_struct = len(struct_topic)
            if len_struct == 5:
                if isinstance(self.access_service.current_agent, AgentBackend):
                    return

                backend_domain, destination, unit_uuid, topic_name, *_ = (
                    struct_topic
                )
                unit_uuid = is_valid_uuid(unit_uuid, UuidEntity.UNIT)

                if destination in [
                    DestinationTopicType.INPUT_BASE_TOPIC,
                    DestinationTopicType.OUTPUT_BASE_TOPIC,
                ]:
                    if self.access_service.current_agent.uuid != unit_uuid:
                        msg = "Available only for a docked Unit"
                        raise NoAccessError(
                            msg, code=ErrorCode.ACCESS_DOCKED_UNIT_ONLY
                        )
                else:
                    msg = f"Topic destination {destination} is invalid, available {list(DestinationTopicType)}"
                    raise NoAccessError(
                        msg, code=ErrorCode.ACCESS_TOPIC_DESTINATION_INVALID
                    )

            elif len_struct in [2, 3]:
                backend_domain, unit_io_uuid, *_ = struct_topic

                if (
                    unit_io_uuid == "+"
                    and self.access_service.current_agent.type
                    == AgentType.BACKEND
                ):
                    return

                unit_io_uuid = is_valid_uuid(unit_io_uuid, UuidEntity.UNIT_IO)

                unit_io = self.unit_io_repository.get(
                    UnitIO(uuid=unit_io_uuid)
                )
                is_valid_object(unit_io, NotFoundEntity.UNIT_IO)

                self.access_service.authorization.check_visibility(unit_io)
            else:
                msg = f"Topic struct is invalid, len {len_struct}, available - [2, 3]"
                raise MqttError(msg, code=ErrorCode.MQTT_TOPIC_STRUCT)
        else:
            msg = "Only for Unit available topic communication"
            raise MqttError(msg, code=ErrorCode.MQTT_UNIT_TOPIC_ONLY)

    def delete(self, uuid: uuid_pkg.UUID) -> None:
        self.access_service.authorization.check_access([AgentType.USER])

        unit = self.unit_repository.get(Unit(uuid=uuid))
        is_valid_object(unit, NotFoundEntity.UNIT)

        self.access_service.authorization.check_ownership(
            unit, [OwnershipType.CREATOR]
        )

        count, unit_ios = self.unit_io_repository.list(
            UnitIOFilter.unlimited(unit_uuid=unit.uuid)
        )

        # orm feature =_=
        unit_deep = copy.deepcopy(unit)
        unit_ios_deep = copy.deepcopy(unit_ios)

        self.unit_repository.delete(unit)

        # clickhouse data clear
        self.unit_io_service.data_pipe_repository.bulk_delete(
            [unit_io.uuid for unit_io in unit_ios_deep]
        )
        self.unit_log_repository.delete(unit_deep.uuid)

    def list(
        self,
        filters: UnitFilter,
        is_include_output_unit_ios: bool = False,
    ) -> tuple[int, list[tuple[Unit, list[dict]]]]:
        self.access_service.authorization.check_access(
            [AgentType.BOT, AgentType.USER, AgentType.UNIT]
        )
        restriction = self.access_service.authorization.access_restriction(
            resource_type=PermissionEntities.UNIT
        )

        filters.visibility_level = (
            self.access_service.authorization.get_available_visibility_levels(
                filters.visibility_level, restriction
            )
        )
        return self.unit_repository.list(
            filters,
            restriction=restriction,
            is_include_output_unit_ios=is_include_output_unit_ios,
        )

    def log_list(
        self, filters: UnitLogFilter
    ) -> tuple[int, builtins.list[UnitLog]]:
        self.access_service.authorization.check_access(
            [AgentType.USER, AgentType.UNIT]
        )

        unit = self.unit_repository.get(Unit(uuid=filters.uuid))
        is_valid_object(unit, NotFoundEntity.UNIT)

        self.access_service.authorization.check_ownership(
            unit, [OwnershipType.CREATOR, OwnershipType.UNIT]
        )

        return self.unit_log_repository.list(filters)

    def get_unit_logs_file(self, uuid: uuid_pkg.UUID) -> tuple[str, str]:
        self.access_service.authorization.check_access(
            [AgentType.USER, AgentType.UNIT]
        )

        unit = self.unit_repository.get(Unit(uuid=uuid))
        is_valid_object(unit, NotFoundEntity.UNIT)

        self.access_service.authorization.check_ownership(
            unit, [OwnershipType.CREATOR, OwnershipType.UNIT]
        )

        _, logs = self.unit_log_repository.list(
            UnitLogFilter.unlimited(
                uuid=uuid,
                level=[item.value for item in LogLevel],
                order_by_create_date=OrderByDate.asc,
            )
        )

        log_filepath = f"tmp/{uuid}_{uuid_pkg.uuid4()}.log"
        with open(log_filepath, "w", encoding="utf-8") as handle:
            handle.writelines(f"{log.to_log_line()}\n" for log in logs)

        return log_filepath, f"{unit.name}.log"

    def bulk_update_units_firmware(self) -> str:
        _, units = self.unit_repository.list(
            UnitFilter.unlimited(is_auto_update_unit=True)
        )
        logging.info(f"{len(units)} units update launched")

        success = 0
        error = 0
        for unit, _nodes in units:
            try:
                repo = self.repo_repository.get(Repo(uuid=unit.repo_uuid))
                is_valid_object(repo, NotFoundEntity.REPO)
                self.sync_state_unit_ios_for_version(unit, repo)
                self.unit_io_service.command_to_input_base_topic(
                    uuid=unit.uuid,
                    command=BackendTopicCommand.UPDATE,
                    is_auto_update=True,
                )
                success += 1
            except Exception as exc:
                logging.warning(f"Failed update unit {unit.uuid} {exc}")
                error += 1

        return f"Updated {success}, failed {error}"

    def schedule_bulk_update_units_firmware(self) -> OperationTask:
        self.access_service.authorization.check_access(
            [AgentType.USER],
            [UserRole.ADMIN],
        )
        task = self.operation_task_service.create(
            OperationTaskCreate(
                task_type=OperationTaskType.UPDATE_ALL_UNITS_FIRMWARE,
            )
        )

        def operation(_db):
            with BackgroundService() as services:
                return services.get_unit_service().bulk_update_units_firmware()

        self.operation_task_service.schedule(task, operation)
        return task

    def generate_current_schema(
        self,
        unit: Unit,
        repo: Repo,
        target_version: str,
    ) -> dict:
        nodes_with_links = self.unit_io_repository.get_nodes_with_links(
            unit.uuid
        )

        output_dict = {}
        input_dict = {}
        for io_uuid, topic_name, topic_type, links in nodes_with_links:
            link_topic_list = []
            if links is not None:
                for output_uuid, output_topic_name in links:
                    link_topic_list.append(
                        get_topic_name(output_uuid, output_topic_name)
                    )

            topics = [get_topic_name(io_uuid, topic_name)] + link_topic_list

            if topic_type == UnitIOTypeEnum.INPUT:
                input_dict[topic_name] = topics
            else:
                output_dict[topic_name] = topics

        schema_dict = self.git_repo_repository.get_schema_dict(
            repo, target_version
        )

        new_schema_dict = {}
        for destination, topics in schema_dict.items():
            new_schema_dict[destination] = {}

            for topic in topics:
                if destination in [
                    DestinationTopicType.INPUT_BASE_TOPIC,
                    DestinationTopicType.OUTPUT_BASE_TOPIC,
                ]:
                    new_schema_dict[destination][topic] = [
                        f"{settings.pu_domain}/{destination}/{unit.uuid}/{topic}"
                    ]
                elif destination == DestinationTopicType.INPUT_TOPIC:
                    new_schema_dict[destination][topic] = input_dict[topic]
                elif destination == DestinationTopicType.OUTPUT_TOPIC:
                    new_schema_dict[destination][topic] = output_dict[topic]

        return new_schema_dict

    def generate_token(self, uuid: uuid_pkg.UUID) -> str:
        unit = self.unit_repository.get(Unit(uuid=uuid))
        is_valid_object(unit, NotFoundEntity.UNIT)

        return AgentUnit(**unit.dict()).generate_agent_token()

    def gen_env_dict(self, uuid: uuid_pkg.UUID) -> dict:
        return {
            ReservedEnvVariableName.PU_DOMAIN: settings.pu_domain,
            ReservedEnvVariableName.PU_HTTP_TYPE: settings.pu_http_type,
            ReservedEnvVariableName.PU_APP_PREFIX: settings.pu_app_prefix,
            ReservedEnvVariableName.PU_API_ACTUAL_PREFIX: settings.pu_api_v1_prefix,
            ReservedEnvVariableName.PU_MQTT_HOST: settings.pu_mqtt_host,
            ReservedEnvVariableName.PU_MQTT_PORT: settings.pu_mqtt_port,
            ReservedEnvVariableName.PU_AUTH_TOKEN: self.generate_token(uuid),
            ReservedEnvVariableName.PU_SECRET_KEY: base64.b64encode(
                os.urandom(32)
            ).decode("utf-8"),
            ReservedEnvVariableName.PU_ENCRYPT_KEY: base64.b64encode(
                os.urandom(32)
            ).decode("utf-8"),
            ReservedEnvVariableName.PU_MQTT_PING_INTERVAL: 20,
            ReservedEnvVariableName.PU_MQTT_KEEPALIVE: runtime.get().pu_mqtt_keepalive,
            ReservedEnvVariableName.PU_STATE_SEND_INTERVAL: (
                runtime.get().pu_instance_unit_state_send_interval
            ),
            ReservedEnvVariableName.PU_MIN_LOG_LEVEL: LogLevel.DEBUG.value,
            ReservedEnvVariableName.PU_MAX_LOG_LENGTH: 64,
        }

    def generate_unified_env(
        self,
        unit: Unit,
        repo: Repo,
        target_version: str,
        user_env_dict: dict | None = None,
        include_commit_version: bool = True,
        filter_by_allowed_keys: bool = True,
    ) -> dict:
        """
        Priority, 1-Upper, 4-Lower:
        1. user_env_dict - env, user write env
        2. current_env_dict - env of unit.cipher_env_dict - if exist
        3. gen_env_dict - pepeunit generating env
        4. target_env_dict - programmer unit template from repository - schema_example.json

        """
        target_env_dict = self.git_repo_repository.get_env_dict(
            repo, target_version
        )

        gen_env_dict = self.gen_env_dict(unit.uuid)

        current_env_dict = None
        if unit.cipher_env_dict:
            current_env_dict = is_valid_json(
                aes_gcm_decode(unit.cipher_env_dict), JsonPayload.CIPHER_ENV
            )

        merged_env_dict = target_env_dict.copy()

        merged_env_dict = merge_two_dict_first_priority(
            gen_env_dict, merged_env_dict
        )

        if current_env_dict:
            merged_env_dict = merge_two_dict_first_priority(
                current_env_dict, merged_env_dict
            )

        if user_env_dict:
            merged_env_dict = merge_two_dict_first_priority(
                user_env_dict, merged_env_dict
            )

        if (
            ReservedEnvVariableName.PU_COMMIT_VERSION.value in merged_env_dict
            and not include_commit_version
        ):
            del merged_env_dict[
                ReservedEnvVariableName.PU_COMMIT_VERSION.value
            ]

        if filter_by_allowed_keys:
            env_example_dict = self.git_repo_repository.get_env_example(
                repo, target_version
            )
            allowed_keys = set(env_example_dict.keys()) | set(
                gen_env_dict.keys()
            )
            merged_env_dict = {
                k: v for k, v in merged_env_dict.items() if k in allowed_keys
            }

        if include_commit_version:
            merged_env_dict[
                ReservedEnvVariableName.PU_COMMIT_VERSION.value
            ] = target_version

        return merged_env_dict

    @staticmethod
    def is_valid_update_rule(data: Unit | UnitCreate) -> None:
        if (
            data.is_compilable_unit
            and data.is_auto_update_unit
            and not data.is_only_tag_update
        ):
            msg = "Compiled units use only tags when updating automatically"
            raise UnitError(msg, code=ErrorCode.UNIT_AUTOUPDATE_TAGS_ONLY)

        if not data.is_auto_update_unit and (
            not data.target_branch or not data.target_commit
        ):
            msg = "Unit updated manually requires branch and commit to be filled out"
            raise UnitError(
                msg, code=ErrorCode.UNIT_MANUAL_UPDATE_BRANCH_COMMIT
            )

    @staticmethod
    def mapper_unit_to_unit_read(
        unit: tuple[Unit, builtins.list[dict]],
    ) -> UnitRead:
        return UnitRead(
            **unit[0].to_dict(),
            unit_ios=[UnitIORead(**item) for item in unit[1]],
        )

    @staticmethod
    def is_valid_wbits(wbits: int):
        available_values_list = list(
            itertools.chain(range(-15, -8), range(9, 16), range(25, 32))
        )
        if wbits not in available_values_list:
            msg = f"Wbits {wbits} is not valid, available {available_values_list}"
            raise UnitError(msg, code=ErrorCode.UNIT_WBITS_INVALID)

    @staticmethod
    def is_valid_level(level: int):
        available_values_list = list(range(-1, 10))
        if level not in available_values_list:
            msg = f"Level {level} is not valid, available {available_values_list}"
            raise UnitError(msg, code=ErrorCode.UNIT_LEVEL_INVALID)
