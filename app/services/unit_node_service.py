import datetime
import uuid as uuid_pkg
from typing import Union

from fastapi import Depends, HTTPException
from fastapi import status as http_status

from app.domain.permission_model import PermissionBaseType
from app.domain.unit_model import Unit
from app.domain.unit_node_edge_model import UnitNodeEdge
from app.domain.unit_node_model import UnitNode
from app.repositories.enum import DestinationTopicType, PermissionEntities, UnitNodeTypeEnum, UserRole
from app.repositories.unit_node_edge_repository import UnitNodeEdgeRepository
from app.repositories.unit_node_repository import UnitNodeRepository
from app.repositories.unit_repository import UnitRepository
from app.schemas.gql.inputs.unit_node import (
    UnitNodeEdgeCreateInput,
    UnitNodeFilterInput,
    UnitNodeSetStateInput,
    UnitNodeUpdateInput,
)
from app.schemas.pydantic.unit_node import (
    UnitNodeEdgeCreate,
    UnitNodeFilter,
    UnitNodeSetState,
    UnitNodeUpdate,
)
from app.services.access_service import AccessService
from app.services.utils import (
    get_topic_name,
    get_visibility_level_priority,
    merge_two_dict_first_priority,
    remove_none_value_dict,
)
from app.services.validators import is_valid_object, is_valid_uuid, is_valid_visibility_level


class UnitNodeService:
    def __init__(
        self,
        unit_repository: UnitRepository = Depends(),
        unit_node_repository: UnitNodeRepository = Depends(),
        unit_node_edge_repository: UnitNodeEdgeRepository = Depends(),
        access_service: AccessService = Depends(),
    ) -> None:
        self.unit_repository = unit_repository
        self.unit_node_repository = unit_node_repository
        self.unit_node_edge_repository = unit_node_edge_repository
        self.access_service = access_service

    def get(self, uuid: uuid_pkg.UUID) -> UnitNode:
        self.access_service.access_check([UserRole.BOT, UserRole.USER, UserRole.ADMIN], is_unit_available=True)
        unit_node = self.unit_node_repository.get(UnitNode(uuid=uuid))
        self.access_service.visibility_check(unit_node)

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
                unit_nodes_list.append(unit_node)

                for agent in [unit, self.access_service.current_agent]:
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
            if get_visibility_level_priority(unit_node.visibility_level) > get_visibility_level_priority(
                unit.visibility_level
            ):
                unit_node.visibility_level = unit.visibility_level
                update_list.append(unit_node)

        self.unit_node_repository.bulk_save(update_list)

    def update(self, uuid: uuid_pkg.UUID, data: Union[UnitNodeUpdate, UnitNodeUpdateInput]) -> UnitNode:
        self.access_service.access_check([UserRole.USER, UserRole.ADMIN])

        unit_node = self.unit_node_repository.get(UnitNode(uuid=uuid))
        is_valid_object(unit_node)

        self.access_service.access_creator_check(unit_node)

        if data.is_rewritable_input is not None:
            self.is_valid_input_unit_node(unit_node)

        update_unit_node = UnitNode(
            **merge_two_dict_first_priority(remove_none_value_dict(data.dict()), unit_node.dict())
        )
        is_valid_visibility_level(self.unit_repository.get(Unit(uuid=update_unit_node.unit_uuid)), [update_unit_node])

        return self.unit_node_repository.update(uuid, update_unit_node)

    def set_state_input(self, uuid: uuid_pkg.UUID, data: Union[UnitNodeSetState, UnitNodeSetStateInput]) -> UnitNode:
        self.access_service.access_check([UserRole.USER, UserRole.ADMIN], is_unit_available=True)

        unit_node = self.unit_node_repository.get(UnitNode(uuid=uuid))
        is_valid_object(unit_node)
        self.is_valid_input_unit_node(unit_node)
        self.access_service.check_access_unit_to_input_node(unit_node)
        self.access_service.visibility_check(unit_node)

        try:
            from app.schemas.mqtt.topic import mqtt
        except ImportError:
            # this UnitNodeService entity imported in mqtt schema layer
            pass

        mqtt.publish(get_topic_name(unit_node.uuid, unit_node.topic_name), data.state)

        return self.unit_node_repository.update(uuid, UnitNode(**data.dict()))

    def create_node_edge(self, data: Union[UnitNodeEdgeCreate, UnitNodeEdgeCreateInput]) -> UnitNodeEdge:
        data.node_input_uuid = is_valid_uuid(data.node_input_uuid)
        data.node_output_uuid = is_valid_uuid(data.node_output_uuid)

        self.access_service.access_check([UserRole.USER, UserRole.ADMIN])

        output_node = self.unit_node_repository.get(UnitNode(uuid=data.node_output_uuid))
        is_valid_object(output_node)
        self.is_valid_output_unit_node(output_node)
        self.access_service.visibility_check(output_node)

        input_node = self.unit_node_repository.get(UnitNode(uuid=data.node_input_uuid))
        is_valid_object(input_node)
        self.is_valid_input_unit_node(input_node)
        self.access_service.visibility_check(input_node)

        new_edge = UnitNodeEdge(**data.dict())
        new_edge.creator_uuid = self.access_service.current_agent.uuid

        if self.unit_node_edge_repository.check(new_edge):
            raise HTTPException(status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Edge exist")

        return self.unit_node_edge_repository.create(new_edge)

    def get_unit_node_edges(self, unit_uuid: uuid_pkg.UUID) -> tuple[int, list[UnitNodeEdge]]:
        self.access_service.access_check([UserRole.BOT, UserRole.USER, UserRole.ADMIN])

        restriction = self.access_service.access_restriction(resource_type=PermissionEntities.UNIT_NODE)

        filters = UnitNodeFilter(unit_uuid=unit_uuid)

        filters.visibility_level = self.access_service.get_available_visibility_levels(
            filters.visibility_level, restriction
        )

        count, unit_nodes = self.unit_node_repository.list(filters=filters, restriction=restriction)

        return count, self.unit_node_edge_repository.get_by_nodes(unit_nodes)

    def delete_node_edge(self, input_uuid: uuid_pkg.UUID, output_uuid: uuid_pkg.UUID) -> None:
        self.access_service.access_check([UserRole.USER, UserRole.ADMIN])

        unit_node_edge = self.unit_node_edge_repository.get_by_two_uuid(input_uuid, output_uuid)
        is_valid_object(unit_node_edge)

        input_unit = self.unit_node_repository.get(UnitNode(uuid=unit_node_edge.node_input_uuid))
        is_valid_object(input_unit)

        if unit_node_edge.creator_uuid != self.access_service.current_agent.uuid:
            self.access_service.access_creator_check(input_unit)
        else:
            self.access_service.access_creator_check(unit_node_edge)

        return self.unit_node_edge_repository.delete(unit_node_edge.uuid)

    def list(self, filters: Union[UnitNodeFilter, UnitNodeFilterInput]) -> tuple[int, list[UnitNode]]:
        self.access_service.access_check([UserRole.BOT, UserRole.USER, UserRole.ADMIN], is_unit_available=True)
        restriction = self.access_service.access_restriction(resource_type=PermissionEntities.UNIT_NODE)
        filters.visibility_level = self.access_service.get_available_visibility_levels(
            filters.visibility_level, restriction
        )

        return self.unit_node_repository.list(filters, restriction=restriction)

    def set_state(self, unit_node_uuid: uuid_pkg.UUID, state: str) -> UnitNode:
        unit_node = self.unit_node_repository.get(UnitNode(uuid=unit_node_uuid))
        is_valid_object(unit_node)
        unit_node.state = state

        return self.unit_node_repository.update(unit_node.uuid, unit_node)

    @staticmethod
    def is_valid_input_unit_node(unit_node: UnitNode) -> None:
        if unit_node.type != UnitNodeTypeEnum.INPUT:
            raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=f"This Node is not Input")

    @staticmethod
    def is_valid_output_unit_node(unit_node: UnitNode) -> None:
        if unit_node.type != UnitNodeTypeEnum.OUTPUT:
            raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=f"This Node is not Output")
