import datetime
import json
import logging
import uuid as uuid_pkg
from typing import Union

from fastapi import Depends, UploadFile
from strawberry.file_uploads import Upload

from app import settings
from app.configs.errors import CustomException, CustomPermissionError, DataPipeError, MqttError, UnitNodeError
from app.configs.redis import DataPipeConfigAction, send_to_data_pipe_stream
from app.domain.permission_model import PermissionBaseType
from app.domain.repo_model import Repo
from app.domain.repository_registry_model import RepositoryRegistry
from app.domain.unit_model import Unit
from app.domain.unit_node_edge_model import UnitNodeEdge
from app.domain.unit_node_model import UnitNode
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
    OrderByDate,
    OwnershipType,
    PermissionEntities,
    ProcessingPolicyType,
    ReservedInputBaseTopic,
    UnitFirmwareUpdateStatus,
    UnitNodeTypeEnum,
)
from app.repositories.data_pipe_repository import DataPipeRepository
from app.repositories.git_repo_repository import GitRepoRepository
from app.repositories.repo_repository import RepoRepository
from app.repositories.repository_registry_repository import RepositoryRegistryRepository
from app.repositories.unit_log_repository import UnitLogRepository
from app.repositories.unit_node_edge_repository import UnitNodeEdgeRepository
from app.repositories.unit_node_repository import UnitNodeRepository
from app.repositories.unit_repository import UnitRepository
from app.schemas.gql.inputs.unit_node import (
    DataPipeFilterInput,
    UnitNodeEdgeCreateInput,
    UnitNodeFilterInput,
    UnitNodeSetStateInput,
    UnitNodeUpdateInput,
)
from app.schemas.mqtt.utils import publish_to_topic
from app.schemas.pydantic.unit_node import (
    DataPipeFilter,
    DataPipeValidationErrorRead,
    UnitNodeEdgeCreate,
    UnitNodeFilter,
    UnitNodeSetState,
    UnitNodeUpdate,
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
from app.services.validators import is_valid_json, is_valid_object, is_valid_uuid, is_valid_visibility_level
from app.utils.utils import async_chunked, obj_serializer, remove_dict_none
from app.validators.data_pipe import is_valid_data_pipe_config
from app.validators.data_pipe_user_csv import StreamingCSVValidator


class UnitNodeService:
    def __init__(
        self,
        unit_repository: UnitRepository = Depends(),
        repository_registry_repository: RepositoryRegistryRepository = Depends(),
        repo_repository: RepoRepository = Depends(),
        unit_node_repository: UnitNodeRepository = Depends(),
        unit_log_repository: UnitLogRepository = Depends(),
        data_pipe_repository: DataPipeRepository = Depends(),
        unit_node_edge_repository: UnitNodeEdgeRepository = Depends(),
        permission_service: PermissionService = Depends(),
        access_service: AccessService = Depends(),
    ) -> None:
        self.unit_repository = unit_repository
        self.repository_registry_repository = repository_registry_repository
        self.repo_repository = repo_repository
        self.git_repo_repository = GitRepoRepository()
        self.unit_node_repository = unit_node_repository
        self.unit_log_repository = unit_log_repository
        self.data_pipe_repository = data_pipe_repository
        self.unit_node_edge_repository = unit_node_edge_repository
        self.permission_service = permission_service
        self.access_service = access_service

    def get(self, uuid: uuid_pkg.UUID) -> UnitNode:
        self.access_service.authorization.check_access([AgentType.BOT, AgentType.USER, AgentType.UNIT])
        unit_node = self.unit_node_repository.get(UnitNode(uuid=uuid))
        self.access_service.authorization.check_visibility(unit_node)

        is_valid_object(unit_node)
        return unit_node

    def bulk_create(
        self, schema_dict: dict, unit: Unit, is_update: bool = False, input_node: dict = None, output_node: dict = None
    ) -> None:

        unit_nodes_list = []
        agents_default_permission_list = []
        for assignment, topic_list in schema_dict.items():
            for topic in topic_list:

                if is_update:
                    if (assignment == DestinationTopicType.INPUT_TOPIC and topic not in input_node.keys()) or (
                        assignment == DestinationTopicType.OUTPUT_TOPIC and topic not in output_node.keys()
                    ):
                        pass
                    else:
                        continue
                else:
                    if assignment not in [DestinationTopicType.INPUT_TOPIC, DestinationTopicType.OUTPUT_TOPIC]:
                        continue

                unit_node = UnitNode(
                    type=(
                        UnitNodeTypeEnum.INPUT
                        if assignment == DestinationTopicType.INPUT_TOPIC
                        else UnitNodeTypeEnum.OUTPUT
                    ),
                    visibility_level=unit.visibility_level,
                    topic_name=topic,
                    creator_uuid=unit.creator_uuid,
                    unit_uuid=unit.uuid,
                )

                unit_node.create_datetime = datetime.datetime.utcnow()
                unit_node.last_update_datetime = unit_node.create_datetime
                unit_nodes_list.append(unit_node)

                for agent in [unit, User(uuid=self.access_service.current_agent.uuid)]:
                    agents_default_permission_list.append(
                        PermissionBaseType(
                            agent_uuid=agent.uuid,
                            agent_type=agent.__class__.__name__,
                            resource_uuid=unit_node.uuid,
                            resource_type=unit_node.__class__.__name__,
                        )
                    )

        self.unit_node_repository.bulk_save(unit_nodes_list)
        self.access_service.permission_repository.bulk_save(agents_default_permission_list)

    def bulk_update(self, schema_dict: dict, unit: Unit, input_node: dict, output_node: dict) -> None:

        self.bulk_create(schema_dict, unit, True, input_node, output_node)

        unit_node_uuid_delete = []
        for assignment, topic_list in schema_dict.items():
            if assignment == DestinationTopicType.INPUT_TOPIC:
                unit_node_uuid_delete.extend([input_node[topic] for topic in input_node.keys() - set(topic_list)])
            elif assignment == DestinationTopicType.OUTPUT_TOPIC:
                unit_node_uuid_delete.extend([output_node[topic] for topic in output_node.keys() - set(topic_list)])

        self.unit_node_repository.delete(unit_node_uuid_delete)

    def bulk_set_visibility_level(self, unit: Unit):

        count, unit_nodes = self.unit_node_repository.list(filters=UnitNodeFilter(unit_uuid=unit.uuid))

        update_list = []
        for unit_node in unit_nodes:
            if get_visibility_level_priority(unit.visibility_level) > get_visibility_level_priority(
                unit_node.visibility_level
            ):
                unit_node.visibility_level = unit.visibility_level
                unit_node.last_update_datetime = datetime.datetime.utcnow()
                update_list.append(unit_node)

        self.unit_node_repository.bulk_save(update_list)

    async def update(self, uuid: uuid_pkg.UUID, data: Union[UnitNodeUpdate, UnitNodeUpdateInput]) -> UnitNode:
        self.access_service.authorization.check_access([AgentType.USER])

        unit_node = self.unit_node_repository.get(UnitNode(uuid=uuid))
        is_valid_object(unit_node)

        self.access_service.authorization.check_ownership(unit_node, [OwnershipType.CREATOR])

        if data.is_rewritable_input is not None:
            self.is_valid_input_unit_node(unit_node)

        update_unit_node = UnitNode(
            **merge_two_dict_first_priority(remove_none_value_dict(data.dict()), unit_node.dict())
        )
        is_valid_visibility_level(self.unit_repository.get(Unit(uuid=update_unit_node.unit_uuid)), [update_unit_node])

        update_unit_node.last_update_datetime = datetime.datetime.utcnow()

        unit_node_updated = self.unit_node_repository.update(uuid, update_unit_node)

        if data.is_data_pipe_active is not None:
            await send_to_data_pipe_stream(
                DataPipeConfigAction.UPDATE if data.is_data_pipe_active else DataPipeConfigAction.DELETE,
                unit_node_updated.model_dump(),
            )

        return self.unit_node_repository.update(uuid, update_unit_node)

    def set_state_input(self, uuid: uuid_pkg.UUID, data: Union[UnitNodeSetState, UnitNodeSetStateInput]) -> UnitNode:
        self.access_service.authorization.check_access([AgentType.USER, AgentType.UNIT])

        unit_node = self.unit_node_repository.get(UnitNode(uuid=uuid))
        is_valid_object(unit_node)
        self.is_valid_input_unit_node(unit_node)
        self.access_service.authorization.check_ownership(unit_node, [OwnershipType.UNIT_TO_INPUT_NODE])
        self.access_service.authorization.check_visibility(unit_node)

        publish_to_topic(get_topic_name(unit_node.uuid, unit_node.topic_name), data.state)

        return self.unit_node_repository.update(
            uuid, UnitNode(last_update_datetime=datetime.datetime.utcnow(), **data.dict())
        )

    def command_to_input_base_topic(
        self, uuid: uuid_pkg.UUID, command: BackendTopicCommand, is_auto_update: bool = False
    ) -> None:

        if not is_auto_update:
            self.access_service.authorization.check_access([AgentType.USER, AgentType.UNIT])

        unit = self.unit_repository.get(Unit(uuid=uuid))
        is_valid_object(unit)

        if not is_auto_update:
            self.access_service.authorization.check_ownership(unit, [OwnershipType.CREATOR, OwnershipType.UNIT])

        repo = self.repo_repository.get(Repo(uuid=unit.repo_uuid))
        repository_registry = self.repository_registry_repository.get(
            RepositoryRegistry(uuid=repo.repository_registry_uuid)
        )

        self.git_repo_repository.is_valid_firmware_platform(
            repo, repository_registry, unit, unit.target_firmware_platform
        )
        target_version, target_tag = self.git_repo_repository.get_target_unit_version(repo, repository_registry, unit)
        schema_dict = self.git_repo_repository.get_schema_dict(repository_registry, target_version)

        command_to_topic_dict = {
            BackendTopicCommand.UPDATE: ReservedInputBaseTopic.UPDATE,
            BackendTopicCommand.ENV_UPDATE: ReservedInputBaseTopic.ENV_UPDATE,
            BackendTopicCommand.SCHEMA_UPDATE: ReservedInputBaseTopic.SCHEMA_UPDATE,
            BackendTopicCommand.LOG_SYNC: ReservedInputBaseTopic.LOG_SYNC,
        }

        target_topic = command_to_topic_dict[command] + GlobalPrefixTopic.BACKEND_SUB_PREFIX.value
        if target_topic in schema_dict['input_base_topic']:

            update_dict = {'COMMAND': command}

            if command == BackendTopicCommand.UPDATE:
                update_dict['NEW_COMMIT_VERSION'] = target_version

                if repo.is_compilable_repo:
                    links = is_valid_json(repository_registry.releases_data, "Releases for compile repo")[target_tag]
                    platform, link = self.git_repo_repository.find_by_platform(links, unit.target_firmware_platform)

                    update_dict['COMPILED_FIRMWARE_LINK'] = link

            if command == BackendTopicCommand.LOG_SYNC:
                self.unit_log_repository.delete(unit.uuid)

            try:
                publish_to_topic(
                    f"{settings.backend_domain}/{DestinationTopicType.INPUT_BASE_TOPIC}/{unit.uuid}/{target_topic}",
                    update_dict,
                )
                if command == BackendTopicCommand.UPDATE:
                    unit.firmware_update_error = None
                    unit.last_firmware_update_datetime = datetime.datetime.utcnow()
                    unit.firmware_update_status = UnitFirmwareUpdateStatus.REQUEST_SENT
            except MqttError as e:
                if command == BackendTopicCommand.UPDATE:
                    unit.firmware_update_error = e.message
                    unit.last_firmware_update_datetime = None
                    unit.firmware_update_status = UnitFirmwareUpdateStatus.ERROR

            if command == BackendTopicCommand.UPDATE:
                self.unit_repository.update(unit.uuid, unit)

    def create_node_edge(self, data: Union[UnitNodeEdgeCreate, UnitNodeEdgeCreateInput]) -> UnitNodeEdge:
        data.node_input_uuid = is_valid_uuid(data.node_input_uuid)
        data.node_output_uuid = is_valid_uuid(data.node_output_uuid)

        self.access_service.authorization.check_access([AgentType.USER])

        output_node = self.unit_node_repository.get(UnitNode(uuid=data.node_output_uuid))
        is_valid_object(output_node)
        self.is_valid_output_unit_node(output_node)
        self.access_service.authorization.check_visibility(output_node)

        input_node = self.unit_node_repository.get(UnitNode(uuid=data.node_input_uuid))
        is_valid_object(input_node)
        self.is_valid_input_unit_node(input_node)
        self.access_service.authorization.check_visibility(input_node)

        new_edge = UnitNodeEdge(**data.dict())
        new_edge.creator_uuid = self.access_service.current_agent.uuid

        if self.unit_node_edge_repository.check(new_edge):
            raise UnitNodeError('Edge exist')

        try:
            self.permission_service.create_by_domains(Unit(uuid=output_node.unit_uuid), input_node)
        except CustomPermissionError:
            pass

        try:
            self.permission_service.create_by_domains(Unit(uuid=input_node.unit_uuid), output_node)
        except CustomPermissionError:
            pass

        try:
            self.permission_service.create_by_domains(Unit(uuid=output_node.unit_uuid), Unit(uuid=input_node.unit_uuid))
        except CustomPermissionError:
            pass

        unit_node_edge = self.unit_node_edge_repository.create(new_edge)

        self.command_to_input_base_topic(
            uuid=input_node.unit_uuid,
            command=BackendTopicCommand.SCHEMA_UPDATE,
            is_auto_update=True,
        )

        return unit_node_edge

    def get_unit_node_edges(self, unit_uuid: uuid_pkg.UUID) -> tuple[int, list[UnitNodeEdge]]:
        self.access_service.authorization.check_access([AgentType.BOT, AgentType.USER])

        restriction = self.access_service.authorization.access_restriction(resource_type=PermissionEntities.UNIT_NODE)

        filters = UnitNodeFilter(unit_uuid=unit_uuid)

        filters.visibility_level = self.access_service.authorization.get_available_visibility_levels(
            filters.visibility_level, restriction
        )

        count, unit_nodes = self.unit_node_repository.list(filters=filters, restriction=restriction)

        return count, self.unit_node_edge_repository.get_by_nodes(unit_nodes)

    async def check_data_pipe_config(self, data_pipe: Union[Upload, UploadFile]) -> list[DataPipeValidationErrorRead]:
        self.access_service.authorization.check_access(
            [AgentType.BOT, AgentType.USER, AgentType.UNIT, AgentType.BACKEND]
        )

        data_pipe_dict = await yml_file_to_dict(data_pipe)

        return is_valid_data_pipe_config(data_pipe_dict, is_business_validator=False)

    async def set_data_pipe_config(self, uuid: uuid_pkg.UUID, data_pipe: Union[Upload, UploadFile]) -> None:
        self.access_service.authorization.check_access([AgentType.USER])

        unit_node = self.unit_node_repository.get(UnitNode(uuid=uuid))
        is_valid_object(unit_node)

        self.access_service.authorization.check_ownership(unit_node, [OwnershipType.CREATOR])

        self.is_valid_active_data_pipe(unit_node)

        data_pipe_dict = await yml_file_to_dict(data_pipe)
        data_pipe_entity = is_valid_data_pipe_config(data_pipe_dict, is_business_validator=True)

        unit_node.data_pipe_yml = json.dumps(data_pipe_entity.dict(), default=obj_serializer)
        unit_node = self.unit_node_repository.update(uuid, unit_node)

        await send_to_data_pipe_stream(DataPipeConfigAction.UPDATE, unit_node.model_dump())

    def get_data_pipe_config(self, uuid: uuid_pkg.UUID) -> str:
        self.access_service.authorization.check_access([AgentType.USER])

        unit_node = self.unit_node_repository.get(UnitNode(uuid=uuid))
        is_valid_object(unit_node)

        self.is_valid_active_data_pipe(unit_node)
        self.is_valid_filled_config(unit_node)

        return dict_to_yml_file(remove_dict_none(is_valid_json(unit_node.data_pipe_yml, "DataPipe config")))

    def delete_data_pipe_data(self, uuid: uuid_pkg.UUID) -> None:
        self.access_service.authorization.check_access([AgentType.USER])

        unit_node = self.unit_node_repository.get(UnitNode(uuid=uuid))
        is_valid_object(unit_node)

        self.access_service.authorization.check_ownership(unit_node, [OwnershipType.CREATOR])

        self.data_pipe_repository.bulk_delete([unit_node.uuid])

    def get_data_pipe_data(
        self, filters: Union[DataPipeFilter, DataPipeFilterInput]
    ) -> tuple[int, list[Union[NRecords, TimeWindow, Aggregation, LastValue]]]:
        self.access_service.authorization.check_access([AgentType.USER, AgentType.UNIT])

        unit_node = self.unit_node_repository.get(UnitNode(uuid=filters.uuid))
        is_valid_object(unit_node)

        self.access_service.authorization.check_ownership(unit_node, [OwnershipType.CREATOR, OwnershipType.UNIT])

        return self.data_pipe_repository.list(filters=filters)

    def get_data_pipe_data_csv(self, uuid: uuid_pkg.UUID) -> str:
        self.access_service.authorization.check_access([AgentType.USER, AgentType.UNIT])

        unit_node = self.unit_node_repository.get(UnitNode(uuid=uuid))
        is_valid_object(unit_node)

        self.access_service.authorization.check_ownership(unit_node, [OwnershipType.CREATOR, OwnershipType.UNIT])

        self.is_valid_active_data_pipe(unit_node)
        self.is_valid_filled_config(unit_node)

        data_pipe_entity = is_valid_data_pipe_config(json.loads(unit_node.data_pipe_yml), is_business_validator=True)
        self.is_valid_policy(data_pipe_entity)

        count, data = self.data_pipe_repository.list(
            filters=DataPipeFilter(
                uuid=uuid,
                type=data_pipe_entity.processing_policy.policy_type,
                order_by_create_date=OrderByDate.asc,
            )
        )

        return self.data_pipe_repository.models_to_csv(data)

    async def set_data_pipe_data_csv(self, uuid: uuid_pkg.UUID, data_csv: Union[Upload, UploadFile]) -> None:
        self.access_service.authorization.check_access([AgentType.USER])

        unit_node = self.unit_node_repository.get(UnitNode(uuid=uuid))
        is_valid_object(unit_node)

        self.access_service.authorization.check_ownership(unit_node, [OwnershipType.CREATOR])

        self.is_valid_active_data_pipe(unit_node)
        self.is_valid_filled_config(unit_node)

        data_pipe_entity = is_valid_data_pipe_config(json.loads(unit_node.data_pipe_yml), is_business_validator=True)
        self.is_valid_policy(data_pipe_entity)

        self.data_pipe_repository.bulk_delete([unit_node.uuid])

        async for batch in async_chunked(
            StreamingCSVValidator(data_pipe_entity).iter_validated_streaming(unit_node.uuid, data_csv), 5000
        ):
            self.data_pipe_repository.bulk_create(data_pipe_entity.processing_policy.policy_type, batch)

    def delete_node_edge(self, input_uuid: uuid_pkg.UUID, output_uuid: uuid_pkg.UUID) -> None:
        self.access_service.authorization.check_access([AgentType.USER])

        unit_node_edge = self.unit_node_edge_repository.get_by_two_uuid(input_uuid, output_uuid)
        is_valid_object(unit_node_edge)

        input_node = self.unit_node_repository.get(UnitNode(uuid=unit_node_edge.node_input_uuid))
        is_valid_object(input_node)

        output_node = self.unit_node_repository.get(UnitNode(uuid=unit_node_edge.node_output_uuid))
        is_valid_object(output_node)

        if unit_node_edge.creator_uuid != self.access_service.current_agent.uuid:
            self.access_service.authorization.check_ownership(input_node, [OwnershipType.CREATOR])
        else:
            self.access_service.authorization.check_ownership(unit_node_edge, [OwnershipType.CREATOR])

        try:
            self.permission_service.delete(output_node.unit_uuid, input_uuid, is_api=False)
        except CustomException as ex:
            logging.info(ex.message)
            # At the time of deletion, the user may have already deleted access,
            # so there should be immunity to this error.
            pass

        self.unit_node_edge_repository.delete(unit_node_edge)

        self.command_to_input_base_topic(
            uuid=input_node.unit_uuid,
            command=BackendTopicCommand.SCHEMA_UPDATE,
            is_auto_update=True,
        )

    def list(self, filters: Union[UnitNodeFilter, UnitNodeFilterInput]) -> tuple[int, list[UnitNode]]:
        self.access_service.authorization.check_access([AgentType.BOT, AgentType.USER, AgentType.UNIT])
        restriction = self.access_service.authorization.access_restriction(resource_type=PermissionEntities.UNIT_NODE)
        filters.visibility_level = self.access_service.authorization.get_available_visibility_levels(
            filters.visibility_level, restriction
        )

        return self.unit_node_repository.list(filters, restriction=restriction)

    def set_state(self, unit_node_uuid: uuid_pkg.UUID, state: str) -> UnitNode:
        unit_node = self.unit_node_repository.get(UnitNode(uuid=unit_node_uuid))
        is_valid_object(unit_node)
        unit_node.state = state
        unit_node.last_update_datetime = datetime.datetime.utcnow()

        return self.unit_node_repository.update(unit_node.uuid, unit_node)

    @staticmethod
    def is_valid_input_unit_node(unit_node: UnitNode) -> None:
        if unit_node.type != UnitNodeTypeEnum.INPUT:
            raise UnitNodeError('This Node {} is not Input'.format(unit_node.uuid))

    @staticmethod
    def is_valid_output_unit_node(unit_node: UnitNode) -> None:
        if unit_node.type != UnitNodeTypeEnum.OUTPUT:
            raise UnitNodeError('This Node {} is not Output'.format(unit_node.uuid))

    @staticmethod
    def is_valid_active_data_pipe(unit_node: UnitNode) -> None:
        if not unit_node.is_data_pipe_active:
            raise DataPipeError('Data pipe is not active')

    @staticmethod
    def is_valid_filled_config(unit_node: UnitNode) -> None:
        if not unit_node.data_pipe_yml:
            raise DataPipeError('Data pipe is not filled')

    @staticmethod
    def is_valid_policy(data_pipe_entity: DataPipeValidationErrorRead) -> None:
        if data_pipe_entity.processing_policy.policy_type == ProcessingPolicyType.LAST_VALUE:
            raise DataPipeError("LastValue type is not supported on this function")
