import contextlib
import datetime
import json
import logging
import uuid as uuid_pkg

from fastapi import Depends

from app import runtime, settings
from app.configs.error_codes import ErrorCode
from app.configs.errors import (
    CustomException,
    CustomPermissionError,
    DataPipeError,
    FeatureFlagError,
    MqttError,
    UnitIOError,
)
from app.configs.redis import DataPipeConfigAction, send_to_data_pipe_stream
from app.domain.link_model import Link
from app.domain.permission_model import PermissionBaseType
from app.domain.repo_model import Repo
from app.domain.unit_io_model import UnitIO
from app.domain.unit_model import Unit
from app.domain.user_model import User
from app.dto.clickhouse.aggregation import Aggregation
from app.dto.clickhouse.last_value import LastValue
from app.dto.clickhouse.n_records import NRecords
from app.dto.clickhouse.time_window import TimeWindow
from app.dto.enum import (
    AgentType,
    BackendTopicCommand,
    DestinationTopicType,
    GlobalPrefixTopic,
    JsonPayload,
    NotFoundEntity,
    OrderByDate,
    OwnershipType,
    PermissionEntities,
    ProcessingPolicyType,
    ReservedEnvVariableName,
    ReservedInputBaseTopic,
    UnitFirmwareUpdateStatus,
    UnitIOTypeEnum,
    UuidEntity,
)
from app.repositories.data_pipe_repository import DataPipeRepository
from app.repositories.git_repo_repository import GitRepoRepository
from app.repositories.link_repository import LinkRepository
from app.repositories.repo_repository import (
    RepoRepository,
)
from app.repositories.unit_io_repository import UnitIORepository
from app.repositories.unit_log_repository import UnitLogRepository
from app.repositories.unit_repository import UnitRepository
from app.schemas.mqtt.utils import publish_to_topic
from app.schemas.pydantic.unit_io import (
    DataPipeFilter,
    DataPipeValidationErrorRead,
    LinkCreate,
    UnitIOFilter,
    UnitIOSetState,
    UnitIOUpdate,
)
from app.services.access_service import AccessService
from app.services.permission_service import PermissionService
from app.services.utils import (
    dict_to_yml_file,
    get_topic_name,
    get_visibility_level_priority,
    merge_two_dict_first_priority,
    remove_none_value_dict,
    yml_file_to_dict,
)
from app.services.validators import (
    is_valid_json,
    is_valid_object,
    is_valid_uuid,
    is_valid_visibility_level,
)
from app.utils.utils import async_chunked, obj_serializer, remove_dict_none
from app.validators.data_pipe import is_valid_data_pipe_config
from app.validators.data_pipe_user_csv import StreamingCSVValidator


class UnitIOService:
    def __init__(
        self,
        unit_repository: UnitRepository = Depends(),
        repo_repository: RepoRepository = Depends(),
        unit_io_repository: UnitIORepository = Depends(),
        unit_log_repository: UnitLogRepository = Depends(),
        data_pipe_repository: DataPipeRepository = Depends(),
        link_repository: LinkRepository = Depends(),
        permission_service: PermissionService = Depends(),
        access_service: AccessService = Depends(),
    ) -> None:
        self.unit_repository = unit_repository
        self.repo_repository = repo_repository
        self.git_repo_repository = GitRepoRepository()
        self.unit_io_repository = unit_io_repository
        self.unit_log_repository = unit_log_repository
        self.data_pipe_repository = data_pipe_repository
        self.link_repository = link_repository
        self.permission_service = permission_service
        self.access_service = access_service

    def get(self, uuid: uuid_pkg.UUID) -> UnitIO:
        self.access_service.authorization.check_access(
            [AgentType.BOT, AgentType.USER, AgentType.UNIT]
        )
        unit_io = self.unit_io_repository.get(UnitIO(uuid=uuid))
        self.access_service.authorization.check_visibility(unit_io)

        is_valid_object(unit_io, NotFoundEntity.UNIT_IO)
        return unit_io

    def bulk_create(
        self,
        schema_dict: dict,
        unit: Unit,
        is_update: bool = False,
        input_node: dict = None,
        output_node: dict = None,
    ) -> None:
        unit_ios_list = []
        agents_default_permission_list = []
        for assignment, topic_list in schema_dict.items():
            for topic in topic_list:
                if is_update:
                    if (
                        assignment == DestinationTopicType.INPUT_TOPIC
                        and topic not in input_node
                    ) or (
                        assignment == DestinationTopicType.OUTPUT_TOPIC
                        and topic not in output_node
                    ):
                        pass
                    else:
                        continue
                elif assignment not in [
                    DestinationTopicType.INPUT_TOPIC,
                    DestinationTopicType.OUTPUT_TOPIC,
                ]:
                    continue

                unit_io = UnitIO(
                    type=(
                        UnitIOTypeEnum.INPUT
                        if assignment == DestinationTopicType.INPUT_TOPIC
                        else UnitIOTypeEnum.OUTPUT
                    ),
                    visibility_level=unit.visibility_level,
                    topic_name=topic,
                    creator_uuid=unit.creator_uuid,
                    unit_uuid=unit.uuid,
                )

                if (
                    runtime.get().pu_datapipe_default_last_value_enable
                    and topic.endswith(
                        GlobalPrefixTopic.BACKEND_SUB_PREFIX.value
                    )
                ):
                    unit_io.is_data_pipe_active = True
                    unit_io.data_pipe_yml = json.dumps(
                        {
                            "active_period": {
                                "type": "Permanent",
                                "start": None,
                                "end": None,
                            },
                            "filters": {
                                "type_input_value": "Text",
                                "type_value_filtering": None,
                                "filtering_values": None,
                                "type_value_threshold": None,
                                "threshold_min": None,
                                "threshold_max": None,
                                "max_rate": 5,
                                "last_unique_check": False,
                                "max_size": 100,
                            },
                            "transformations": None,
                            "processing_policy": {
                                "policy_type": "LastValue",
                                "n_records_count": None,
                                "time_window_size": None,
                                "aggregation_functions": None,
                            },
                        }
                    )

                unit_io.create_datetime = datetime.datetime.now(datetime.UTC)
                unit_io.last_update_datetime = unit_io.create_datetime
                unit_ios_list.append(unit_io)

                agents_default_permission_list.extend(
                    [
                        PermissionBaseType(
                            agent_uuid=agent.uuid,
                            agent_type=agent.__class__.__name__,
                            resource_uuid=unit_io.uuid,
                            resource_type=unit_io.__class__.__name__,
                        )
                        for agent in [
                            unit,
                            User(uuid=self.access_service.current_agent.uuid),
                        ]
                    ]
                )

        self.unit_io_repository.bulk_save(unit_ios_list)
        self.access_service.permission_repository.bulk_save(
            agents_default_permission_list
        )

    def bulk_update(
        self,
        schema_dict: dict,
        unit: Unit,
        input_node: dict,
        output_node: dict,
    ) -> None:
        self.bulk_create(schema_dict, unit, True, input_node, output_node)

        unit_io_uuid_delete = []
        for assignment, topic_list in schema_dict.items():
            if assignment == DestinationTopicType.INPUT_TOPIC:
                unit_io_uuid_delete.extend(
                    [
                        input_node[topic]
                        for topic in input_node.keys() - set(topic_list)
                    ]
                )
            elif assignment == DestinationTopicType.OUTPUT_TOPIC:
                unit_io_uuid_delete.extend(
                    [
                        output_node[topic]
                        for topic in output_node.keys() - set(topic_list)
                    ]
                )

        self.unit_io_repository.delete(unit_io_uuid_delete)

    def bulk_set_visibility_level(self, unit: Unit):
        count, unit_ios = self.unit_io_repository.list(
            filters=UnitIOFilter.unlimited(unit_uuid=unit.uuid)
        )

        update_list = []
        for unit_io in unit_ios:
            if get_visibility_level_priority(
                unit.visibility_level
            ) > get_visibility_level_priority(unit_io.visibility_level):
                unit_io.visibility_level = unit.visibility_level
                unit_io.last_update_datetime = datetime.datetime.now(
                    datetime.UTC
                )
                update_list.append(unit_io)

        self.unit_io_repository.bulk_save(update_list)

    async def update(self, uuid: uuid_pkg.UUID, data: UnitIOUpdate) -> UnitIO:
        self.access_service.authorization.check_access([AgentType.USER])

        unit_io = self.unit_io_repository.get(UnitIO(uuid=uuid))
        is_valid_object(unit_io, NotFoundEntity.UNIT_IO)

        self.access_service.authorization.check_ownership(
            unit_io, [OwnershipType.CREATOR]
        )

        if (
            not unit_io.topic_name.endswith(
                GlobalPrefixTopic.BACKEND_SUB_PREFIX.value
            )
            and data.is_data_pipe_active
        ):
            msg = "DataPipe cannot be activated if the topic does not have the suffix /pepeunit"
            raise DataPipeError(msg, code=ErrorCode.DATAPIPE_TOPIC_SUFFIX)

        if data.is_rewritable_input is not None:
            self.is_valid_input_unit_io(unit_io)

        if data.max_connections is not None and data.max_connections < 1:
            msg = "max_connections must be at least 1"
            raise UnitIOError(msg, code=ErrorCode.UNIT_IO_MAX_CONNECTIONS)

        update_unit_io = UnitIO(
            **merge_two_dict_first_priority(
                remove_none_value_dict(data.dict()), unit_io.dict()
            )
        )
        is_valid_visibility_level(
            self.unit_repository.get(Unit(uuid=update_unit_io.unit_uuid)),
            [update_unit_io],
        )

        update_unit_io.last_update_datetime = datetime.datetime.now(
            datetime.UTC
        )

        unit_io_updated = self.unit_io_repository.update(uuid, update_unit_io)

        if (
            runtime.get().pu_ff_datapipe_enable
            and data.is_data_pipe_active is not None
            and unit_io.topic_name.endswith(
                GlobalPrefixTopic.BACKEND_SUB_PREFIX.value
            )
        ):
            await send_to_data_pipe_stream(
                DataPipeConfigAction.UPDATE
                if data.is_data_pipe_active
                else DataPipeConfigAction.DELETE,
                unit_io_updated.model_dump(),
            )

        return self.unit_io_repository.update(uuid, update_unit_io)

    def set_state_input(
        self,
        uuid: uuid_pkg.UUID,
        data: UnitIOSetState,
    ) -> UnitIO:
        self.access_service.authorization.check_access(
            [AgentType.USER, AgentType.UNIT]
        )

        unit_io = self.unit_io_repository.get(UnitIO(uuid=uuid))
        is_valid_object(unit_io, NotFoundEntity.UNIT_IO)
        self.is_valid_input_unit_io(unit_io)
        self.access_service.authorization.check_ownership(
            unit_io, [OwnershipType.UNIT_TO_INPUT_NODE]
        )
        self.access_service.authorization.check_visibility(unit_io)

        publish_to_topic(
            get_topic_name(unit_io.uuid, unit_io.topic_name), data.state
        )

        unit_io.state = data.state
        unit_io.last_update_datetime = datetime.datetime.now(datetime.UTC)
        return self.unit_io_repository.update(uuid, unit_io)

    def command_to_input_base_topic(
        self,
        uuid: uuid_pkg.UUID,
        command: BackendTopicCommand,
        is_auto_update: bool = False,
    ) -> None:
        if not is_auto_update:
            self.access_service.authorization.check_access(
                [AgentType.USER, AgentType.UNIT]
            )

        unit = self.unit_repository.get(Unit(uuid=uuid))
        is_valid_object(unit, NotFoundEntity.UNIT)

        if not is_auto_update:
            self.access_service.authorization.check_ownership(
                unit, [OwnershipType.CREATOR, OwnershipType.UNIT]
            )

        repo = self.repo_repository.get(Repo(uuid=unit.repo_uuid))
        is_valid_object(repo, NotFoundEntity.REPO)

        self.git_repo_repository.is_valid_firmware_platform(
            repo, unit, unit.target_firmware_platform
        )
        target_version, target_tag = (
            self.git_repo_repository.get_target_unit_version(repo, unit)
        )
        schema_dict = self.git_repo_repository.get_schema_dict(
            repo, target_version
        )

        command_to_topic_dict = {
            BackendTopicCommand.UPDATE: ReservedInputBaseTopic.UPDATE.value,
            BackendTopicCommand.ENV_UPDATE: ReservedInputBaseTopic.ENV_UPDATE.value,
            BackendTopicCommand.SCHEMA_UPDATE: ReservedInputBaseTopic.SCHEMA_UPDATE.value,
            BackendTopicCommand.LOG_SYNC: ReservedInputBaseTopic.LOG_SYNC.value,
            BackendTopicCommand.RESET: ReservedInputBaseTopic.RESET.value,
        }

        target_topic = (
            command_to_topic_dict[command]
            + GlobalPrefixTopic.BACKEND_SUB_PREFIX.value
        )
        if target_topic in schema_dict["input_base_topic"]:
            update_message_dict = self._build_message_dict(
                command,
                repo,
                unit,
                target_version,
                target_tag,
            )

            try:
                publish_to_topic(
                    f"{settings.pu_domain}/{DestinationTopicType.INPUT_BASE_TOPIC.value}/{unit.uuid}/{target_topic}",
                    update_message_dict,
                )
                if command == BackendTopicCommand.UPDATE:
                    unit.firmware_update_error = None
                    unit.last_firmware_update_datetime = datetime.datetime.now(
                        datetime.UTC
                    )
                    unit.firmware_update_status = (
                        UnitFirmwareUpdateStatus.REQUEST_SENT
                    )

                    self.unit_repository.update(unit.uuid, unit)

            except MqttError as e:
                if command == BackendTopicCommand.UPDATE:
                    unit.firmware_update_error = e.message
                    unit.last_firmware_update_datetime = None
                    unit.firmware_update_status = (
                        UnitFirmwareUpdateStatus.ERROR
                    )

                    self.unit_repository.update(unit.uuid, unit)

                raise e

    def _build_message_dict(
        self,
        command: BackendTopicCommand,
        repo: Repo,
        unit: Unit,
        target_version: str,
        target_tag: str,
    ) -> dict:
        message_dict = {"COMMAND": command}

        if command == BackendTopicCommand.UPDATE:
            message_dict[ReservedEnvVariableName.PU_COMMIT_VERSION.value] = (
                target_version
            )
            if unit.is_compilable_unit:
                links = is_valid_json(
                    repo.releases_data,
                    JsonPayload.RELEASES_FOR_COMPILE_REPO_TITLE,
                )[target_tag]
                _, link = self.git_repo_repository.find_by_platform(
                    links, unit.target_firmware_platform
                )
                message_dict["COMPILED_FIRMWARE_LINK"] = link

        elif command == BackendTopicCommand.LOG_SYNC:
            self.unit_log_repository.delete(unit.uuid)

        return message_dict

    def create_link(self, data: LinkCreate) -> Link:
        data.input_uuid = is_valid_uuid(
            data.input_uuid, UuidEntity.UNIT_IO_INPUT
        )
        data.output_uuid = is_valid_uuid(
            data.output_uuid, UuidEntity.UNIT_IO_OUTPUT
        )

        self.access_service.authorization.check_access([AgentType.USER])

        output_node = self.unit_io_repository.get(
            UnitIO(uuid=data.output_uuid)
        )
        is_valid_object(output_node, NotFoundEntity.UNIT_IO)
        self.is_valid_output_unit_io(output_node)
        self.access_service.authorization.check_visibility(output_node)

        input_node = self.unit_io_repository.get(UnitIO(uuid=data.input_uuid))
        is_valid_object(input_node, NotFoundEntity.UNIT_IO)
        self.is_valid_input_unit_io(input_node)
        self.access_service.authorization.check_visibility(input_node)

        # Check connection limit for input node (incoming connections)
        current_input_connections = self.link_repository.count_by_input_node(
            input_node.uuid
        )
        if current_input_connections >= input_node.max_connections:
            msg = f"Maximum number of incoming connections ({input_node.max_connections}) reached for input node {input_node.uuid}"
            raise UnitIOError(
                msg, code=ErrorCode.UNIT_IO_INPUT_CONNECTION_LIMIT
            )

        # Check connection limit for output node (outgoing connections)
        current_output_connections = self.link_repository.count_by_output_node(
            output_node.uuid
        )
        if current_output_connections >= output_node.max_connections:
            msg = f"Maximum number of outgoing connections ({output_node.max_connections}) reached for output node {output_node.uuid}"
            raise UnitIOError(
                msg, code=ErrorCode.UNIT_IO_OUTPUT_CONNECTION_LIMIT
            )

        new_link = Link(**data.dict())
        new_link.creator_uuid = self.access_service.current_agent.uuid

        if self.link_repository.check(new_link):
            msg = "Link exist"
            raise UnitIOError(msg, code=ErrorCode.LINK_EXISTS)

        with contextlib.suppress(CustomPermissionError):
            self.permission_service.create_by_domains(
                Unit(uuid=output_node.unit_uuid), input_node
            )

        with contextlib.suppress(CustomPermissionError):
            self.permission_service.create_by_domains(
                Unit(uuid=input_node.unit_uuid), output_node
            )

        with contextlib.suppress(CustomPermissionError):
            self.permission_service.create_by_domains(
                Unit(uuid=output_node.unit_uuid),
                Unit(uuid=input_node.unit_uuid),
            )

        link = self.link_repository.create(new_link)

        with contextlib.suppress(MqttError):
            self.command_to_input_base_topic(
                uuid=input_node.unit_uuid,
                command=BackendTopicCommand.SCHEMA_UPDATE,
                is_auto_update=True,
            )

        return link

    def get_links(self, unit_uuid: uuid_pkg.UUID) -> tuple[int, list[Link]]:
        self.access_service.authorization.check_access(
            [AgentType.BOT, AgentType.USER]
        )

        restriction = self.access_service.authorization.access_restriction(
            resource_type=PermissionEntities.UNIT_IO
        )

        filters = UnitIOFilter.unlimited(unit_uuid=unit_uuid)

        filters.visibility_level = (
            self.access_service.authorization.get_available_visibility_levels(
                filters.visibility_level, restriction
            )
        )

        count, unit_ios = self.unit_io_repository.list(
            filters=filters, restriction=restriction
        )

        return count, self.link_repository.get_by_nodes(unit_ios)

    async def check_data_pipe_config(
        self, data_pipe
    ) -> list[DataPipeValidationErrorRead]:
        if not runtime.get().pu_ff_datapipe_enable:
            msg = "This feature has been disabled by the instance Owner"
            raise FeatureFlagError(msg, code=ErrorCode.FEATURE_DISABLED)

        self.access_service.authorization.check_access(
            [AgentType.BOT, AgentType.USER, AgentType.UNIT, AgentType.BACKEND]
        )

        data_pipe_dict = await yml_file_to_dict(data_pipe)

        return is_valid_data_pipe_config(
            data_pipe_dict, is_business_validator=False
        )

    async def set_data_pipe_config(
        self, uuid: uuid_pkg.UUID, data_pipe
    ) -> None:
        if not runtime.get().pu_ff_datapipe_enable:
            msg = "This feature has been disabled by the instance Owner"
            raise FeatureFlagError(msg, code=ErrorCode.FEATURE_DISABLED)

        self.access_service.authorization.check_access([AgentType.USER])

        unit_io = self.unit_io_repository.get(UnitIO(uuid=uuid))
        is_valid_object(unit_io, NotFoundEntity.UNIT_IO)

        self.access_service.authorization.check_ownership(
            unit_io, [OwnershipType.CREATOR]
        )

        self.is_valid_active_data_pipe(unit_io)

        data_pipe_dict = await yml_file_to_dict(data_pipe)
        data_pipe_entity = is_valid_data_pipe_config(
            data_pipe_dict, is_business_validator=True
        )

        unit_io.data_pipe_yml = json.dumps(
            data_pipe_entity.dict(), default=obj_serializer
        )
        unit_io = self.unit_io_repository.update(uuid, unit_io)

        await send_to_data_pipe_stream(
            DataPipeConfigAction.UPDATE, unit_io.model_dump()
        )

    def get_data_pipe_config(self, uuid: uuid_pkg.UUID) -> str:
        if not runtime.get().pu_ff_datapipe_enable:
            msg = "This feature has been disabled by the instance Owner"
            raise FeatureFlagError(msg, code=ErrorCode.FEATURE_DISABLED)

        self.access_service.authorization.check_access([AgentType.USER])

        unit_io = self.unit_io_repository.get(UnitIO(uuid=uuid))
        is_valid_object(unit_io, NotFoundEntity.UNIT_IO)

        self.is_valid_active_data_pipe(unit_io)
        self.is_valid_filled_config(unit_io)

        return dict_to_yml_file(
            remove_dict_none(
                is_valid_json(
                    unit_io.data_pipe_yml, JsonPayload.DATA_PIPE_CONFIG
                )
            )
        )

    def delete_data_pipe_data(self, uuid: uuid_pkg.UUID) -> None:
        if not runtime.get().pu_ff_datapipe_enable:
            msg = "This feature has been disabled by the instance Owner"
            raise FeatureFlagError(msg, code=ErrorCode.FEATURE_DISABLED)

        self.access_service.authorization.check_access([AgentType.USER])

        unit_io = self.unit_io_repository.get(UnitIO(uuid=uuid))
        is_valid_object(unit_io, NotFoundEntity.UNIT_IO)

        self.access_service.authorization.check_ownership(
            unit_io, [OwnershipType.CREATOR]
        )

        self.data_pipe_repository.bulk_delete([unit_io.uuid])

    def get_data_pipe_data(
        self, filters: DataPipeFilter
    ) -> tuple[int, list[NRecords | TimeWindow | Aggregation | LastValue]]:
        if not runtime.get().pu_ff_datapipe_enable:
            msg = "This feature has been disabled by the instance Owner"
            raise FeatureFlagError(msg, code=ErrorCode.FEATURE_DISABLED)

        self.access_service.authorization.check_access(
            [AgentType.USER, AgentType.UNIT]
        )

        unit_io = self.unit_io_repository.get(UnitIO(uuid=filters.uuid))
        is_valid_object(unit_io, NotFoundEntity.UNIT_IO)

        self.access_service.authorization.check_ownership(
            unit_io, [OwnershipType.CREATOR, OwnershipType.UNIT]
        )

        return self.data_pipe_repository.list(filters=filters)

    def get_data_pipe_data_csv(self, uuid: uuid_pkg.UUID) -> str:
        if not runtime.get().pu_ff_datapipe_enable:
            msg = "This feature has been disabled by the instance Owner"
            raise FeatureFlagError(msg, code=ErrorCode.FEATURE_DISABLED)

        self.access_service.authorization.check_access(
            [AgentType.USER, AgentType.UNIT]
        )

        unit_io = self.unit_io_repository.get(UnitIO(uuid=uuid))
        is_valid_object(unit_io, NotFoundEntity.UNIT_IO)

        self.access_service.authorization.check_ownership(
            unit_io, [OwnershipType.CREATOR, OwnershipType.UNIT]
        )

        self.is_valid_active_data_pipe(unit_io)
        self.is_valid_filled_config(unit_io)

        data_pipe_entity = is_valid_data_pipe_config(
            json.loads(unit_io.data_pipe_yml), is_business_validator=True
        )
        self.is_valid_policy(data_pipe_entity)

        count, data = self.data_pipe_repository.list(
            filters=DataPipeFilter.unlimited(
                uuid=uuid,
                type=data_pipe_entity.processing_policy.policy_type,
                order_by_create_date=OrderByDate.asc,
            )
        )

        return self.data_pipe_repository.models_to_csv(data)

    async def set_data_pipe_data_csv(
        self, uuid: uuid_pkg.UUID, data_csv
    ) -> None:
        if not runtime.get().pu_ff_datapipe_enable:
            msg = "This feature has been disabled by the instance Owner"
            raise FeatureFlagError(msg, code=ErrorCode.FEATURE_DISABLED)

        self.access_service.authorization.check_access([AgentType.USER])

        unit_io = self.unit_io_repository.get(UnitIO(uuid=uuid))
        is_valid_object(unit_io, NotFoundEntity.UNIT_IO)

        self.access_service.authorization.check_ownership(
            unit_io, [OwnershipType.CREATOR]
        )

        self.is_valid_active_data_pipe(unit_io)
        self.is_valid_filled_config(unit_io)

        data_pipe_entity = is_valid_data_pipe_config(
            json.loads(unit_io.data_pipe_yml), is_business_validator=True
        )
        self.is_valid_policy(data_pipe_entity)

        self.data_pipe_repository.bulk_delete([unit_io.uuid])

        async for batch in async_chunked(
            StreamingCSVValidator(data_pipe_entity).iter_validated_streaming(
                unit_io.uuid, data_csv
            ),
            5000,
        ):
            self.data_pipe_repository.bulk_create(
                data_pipe_entity.processing_policy.policy_type, batch
            )

    def delete_link(
        self, input_uuid: uuid_pkg.UUID, output_uuid: uuid_pkg.UUID
    ) -> None:
        self.access_service.authorization.check_access([AgentType.USER])

        link = self.link_repository.get_by_two_uuid(input_uuid, output_uuid)
        is_valid_object(link, NotFoundEntity.LINK)

        input_node = self.unit_io_repository.get(UnitIO(uuid=link.input_uuid))
        is_valid_object(input_node, NotFoundEntity.UNIT_IO)

        output_node = self.unit_io_repository.get(
            UnitIO(uuid=link.output_uuid)
        )
        is_valid_object(output_node, NotFoundEntity.UNIT_IO)

        if link.creator_uuid != self.access_service.current_agent.uuid:
            self.access_service.authorization.check_ownership(
                input_node, [OwnershipType.CREATOR]
            )
        else:
            self.access_service.authorization.check_ownership(
                link, [OwnershipType.CREATOR]
            )

        try:
            self.permission_service.delete(
                output_node.unit_uuid, input_uuid, is_api=False
            )
        except CustomException as ex:
            logging.info(ex)
            # At the time of deletion, the user may have already deleted access,
            # so there should be immunity to this error.

        self.link_repository.delete(link)

        with contextlib.suppress(MqttError):
            self.command_to_input_base_topic(
                uuid=input_node.unit_uuid,
                command=BackendTopicCommand.SCHEMA_UPDATE,
                is_auto_update=True,
            )

    def list(self, filters: UnitIOFilter) -> tuple[int, list[UnitIO]]:
        self.access_service.authorization.check_access(
            [AgentType.BOT, AgentType.USER, AgentType.UNIT]
        )
        restriction = self.access_service.authorization.access_restriction(
            resource_type=PermissionEntities.UNIT_IO
        )
        filters.visibility_level = (
            self.access_service.authorization.get_available_visibility_levels(
                filters.visibility_level, restriction
            )
        )

        return self.unit_io_repository.list(filters, restriction=restriction)

    def set_state(self, unit_io_uuid: uuid_pkg.UUID, state: str) -> UnitIO:
        unit_io = self.unit_io_repository.get(UnitIO(uuid=unit_io_uuid))
        is_valid_object(unit_io, NotFoundEntity.UNIT_IO)
        unit_io.state = state
        unit_io.last_update_datetime = datetime.datetime.now(datetime.UTC)

        return self.unit_io_repository.update(unit_io.uuid, unit_io)

    @staticmethod
    def is_valid_input_unit_io(unit_io: UnitIO) -> None:
        if unit_io.type != UnitIOTypeEnum.INPUT:
            msg = f"This Node {unit_io.uuid} is not Input"
            raise UnitIOError(msg, code=ErrorCode.UNIT_IO_NOT_INPUT)

    @staticmethod
    def is_valid_output_unit_io(unit_io: UnitIO) -> None:
        if unit_io.type != UnitIOTypeEnum.OUTPUT:
            msg = f"This Node {unit_io.uuid} is not Output"
            raise UnitIOError(msg, code=ErrorCode.UNIT_IO_NOT_OUTPUT)

    @staticmethod
    def is_valid_active_data_pipe(unit_io: UnitIO) -> None:
        if not unit_io.is_data_pipe_active:
            msg = "Data pipe is not active"
            raise DataPipeError(msg, code=ErrorCode.DATAPIPE_NOT_ACTIVE)

    @staticmethod
    def is_valid_filled_config(unit_io: UnitIO) -> None:
        if not unit_io.data_pipe_yml:
            msg = "Data pipe is not filled"
            raise DataPipeError(msg, code=ErrorCode.DATAPIPE_NOT_FILLED)

    @staticmethod
    def is_valid_policy(data_pipe_entity: DataPipeValidationErrorRead) -> None:
        if (
            data_pipe_entity.processing_policy.policy_type
            == ProcessingPolicyType.LAST_VALUE
        ):
            msg = "LastValue type is not supported on this function"
            raise DataPipeError(
                msg, code=ErrorCode.DATAPIPE_LAST_VALUE_UNSUPPORTED
            )
