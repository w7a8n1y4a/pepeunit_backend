from typing import Union

from fastapi import Depends
from fastapi import HTTPException
from fastapi import status as http_status

from app import settings
from app.domain.unit_node_edge_model import UnitNodeEdge
from app.domain.unit_node_model import UnitNode
from app.repositories.enum import UserRole, UnitNodeTypeEnum, PermissionEntities
from app.repositories.unit_node_edge_repository import UnitNodeEdgeRepository
from app.repositories.unit_node_repository import UnitNodeRepository
from app.schemas.gql.inputs.unit_node import UnitNodeFilterInput, UnitNodeUpdateInput, UnitNodeSetStateInput, \
    UnitNodeEdgeCreateInput

from app.schemas.pydantic.unit_node import UnitNodeFilter, UnitNodeSetState, UnitNodeUpdate, UnitNodeEdgeCreate
from app.services.access_service import AccessService
from app.services.utils import creator_check
from app.services.validators import is_valid_object


class UnitNodeService:
    def __init__(
        self,
        unit_node_repository: UnitNodeRepository = Depends(),
        unit_node_edge_repository: UnitNodeEdgeRepository = Depends(),
        access_service: AccessService = Depends()
    ) -> None:
        self.unit_node_repository = unit_node_repository
        self.unit_node_edge_repository = unit_node_edge_repository
        self.access_service = access_service

    def get(self, uuid: str) -> UnitNode:
        self.access_service.access_check([UserRole.BOT, UserRole.USER, UserRole.ADMIN], is_unit_available=True)
        unit_node = self.unit_node_repository.get(UnitNode(uuid=uuid))
        self.access_service.visibility_check(unit_node)

        is_valid_object(unit_node)
        return unit_node

    def update(self, uuid: str, data: Union[UnitNodeUpdate, UnitNodeUpdateInput]) -> UnitNode:
        self.access_service.access_check([UserRole.USER, UserRole.ADMIN])

        unit_node = self.unit_node_repository.get(UnitNode(uuid=uuid))
        self.access_service.visibility_check(unit_node)

        creator_check(self.access_service.current_agent, unit_node)

        update_unit_node = UnitNode(**data.dict())
        return self.unit_node_repository.update(uuid, update_unit_node)

    def set_state_input(self, uuid: str, data: Union[UnitNodeSetState, UnitNodeSetStateInput]) -> UnitNode:
        self.access_service.access_check([UserRole.USER, UserRole.ADMIN], is_unit_available=True)

        unit_node = self.unit_node_repository.get(UnitNode(uuid=uuid))
        self.access_service.visibility_check(unit_node)
        self.is_valid_input_unit_node(unit_node)

        try:
            from app.schemas.mqtt.topic import mqtt
        except ImportError:
            # this UnitNodeService entity imported in mqtt schema layer
            pass

        mqtt.publish(f"{settings.backend_domain}/input/{unit_node.unit_uuid}/{unit_node.topic_name}", data.state)

        return self.unit_node_repository.update(uuid, UnitNode(**data.dict()))

    def create_node_edge(self, data: Union[UnitNodeEdgeCreate, UnitNodeEdgeCreateInput]) -> UnitNodeEdge:
        self.access_service.access_check([UserRole.USER, UserRole.ADMIN], is_unit_available=True)

        output_node = self.unit_node_repository.get(UnitNode(uuid=data.node_output_uuid))
        is_valid_object(output_node)
        self.is_valid_output_unit_node(output_node)
        self.access_service.visibility_check(output_node)

        input_node = self.unit_node_repository.get(UnitNode(uuid=data.node_input_uuid))
        is_valid_object(input_node)
        self.is_valid_input_unit_node(input_node)
        self.access_service.visibility_check(input_node)

        return self.unit_node_edge_repository.create(UnitNodeEdge(**data.dict()))

    def delete_node_edge(self, uuid: str) -> None:
        self.access_service.access_check([UserRole.USER, UserRole.ADMIN], is_unit_available=True)

        unit_node_edge = self.unit_node_edge_repository.get(UnitNodeEdge(uuid=uuid))
        is_valid_object(unit_node_edge)

        input_unit = self.unit_node_repository.get(UnitNode(uuid=unit_node_edge.node_input_uuid))
        is_valid_object(input_unit)

        self.access_service.visibility_check(input_unit)

        return self.unit_node_edge_repository.delete(unit_node_edge.uuid)

    def list(self, filters: Union[UnitNodeFilter, UnitNodeFilterInput]) -> list[UnitNode]:
        self.access_service.access_check([UserRole.USER, UserRole.ADMIN], is_unit_available=True)
        restriction = self.access_service.access_restriction(resource_type=PermissionEntities.UNIT_NODE)
        filters.visibility_level = self.access_service.get_available_visibility_levels(
            filters.visibility_level, restriction
        )
        return self.unit_node_repository.list(filters, restriction=restriction)

    def set_state(self, unit_uuid: str, topic_name: str, topic_type: str, state: str) -> UnitNode:
        unit_node = self.unit_node_repository.get_by_topic(unit_uuid, UnitNode(topic_name=topic_name, type=topic_type))
        unit_node.state = state

        return self.unit_node_repository.update(unit_node.uuid, unit_node)

    @staticmethod
    def is_valid_input_unit_node(unit_node: UnitNode) -> None:
        if unit_node.type != UnitNodeTypeEnum.INPUT:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST, detail=f"This Node is not Input"
            )

    @staticmethod
    def is_valid_output_unit_node(unit_node: UnitNode) -> None:
        if unit_node.type != UnitNodeTypeEnum.OUTPUT:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST, detail=f"This Node is not Output"
            )
