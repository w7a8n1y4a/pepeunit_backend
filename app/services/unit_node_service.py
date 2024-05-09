from typing import Union

from fastapi import Depends
from fastapi import HTTPException
from fastapi import status as http_status
from sqlmodel import Session

from app import settings
from app.configs.db import get_session
from app.domain.unit_node_model import UnitNode
from app.repositories.enum import UserRole, UnitNodeTypeEnum
from app.repositories.unit_node_repository import UnitNodeRepository
from app.schemas.gql.inputs.unit_node import UnitNodeFilterInput, UnitNodeUpdateInput, UnitNodeSetStateInput

from app.schemas.pydantic.unit_node import UnitNodeFilter, UnitNodeSetState, UnitNodeUpdate
from app.services.access_service import AccessService
from app.services.utils import token_depends
from app.services.validators import is_valid_object


class UnitNodeService:
    def __init__(
        self, db: Session = Depends(get_session),
        jwt_token: str = Depends(token_depends)
    ) -> None:
        self.unit_node_repository = UnitNodeRepository(db)
        self.access_service = AccessService(db, jwt_token)

    def get(self, uuid: str) -> UnitNode:
        self.access_service.access_check([UserRole.USER, UserRole.ADMIN])
        unit_node = self.unit_node_repository.get(UnitNode(uuid=uuid))

        is_valid_object(unit_node)

        print(unit_node)

        return unit_node

    def update(self, uuid: str, data: Union[UnitNodeUpdate, UnitNodeUpdateInput]) -> UnitNode:
        self.access_service.access_check([UserRole.USER])
        update_unit_node = UnitNode(**data.dict())
        return self.unit_node_repository.update(uuid, update_unit_node)

    def set_state_input(self, uuid: str, data: Union[UnitNodeSetState, UnitNodeSetStateInput]) -> UnitNode:
        self.access_service.access_check([UserRole.USER])

        unit_node = self.unit_node_repository.get(UnitNode(uuid=uuid))
        self.is_valid_input_unit_node(unit_node)

        try:
            from app.schemas.mqtt.topic import mqtt
        except ImportError:
            # this UnitNodeService entity imported in mqtt schema layer
            pass

        mqtt.publish(f"{settings.backend_domain}/input/{unit_node.unit_uuid}/{unit_node.topic_name}", data.state)

        return self.unit_node_repository.update(uuid, UnitNode(**data.dict()))

    def set_state(self, unit_uuid: str, topic_name: str, topic_type: str, state: str) -> UnitNode:
        unit_node = self.unit_node_repository.get_by_topic(unit_uuid, UnitNode(topic_name=topic_name, type=topic_type))
        unit_node.state = state

        return self.unit_node_repository.update(unit_node.uuid, unit_node)

    def list(self, filters: Union[UnitNodeFilter, UnitNodeFilterInput]) -> list[UnitNode]:
        self.access_service.access_check([UserRole.USER, UserRole.ADMIN])
        restriction = self.access_service.access_restriction()
        filters.visibility_level = self.access_service.get_available_visibility_levels(
            filters.visibility_level,
            restriction
        )
        return self.unit_node_repository.list(filters, restriction=restriction)

    @staticmethod
    def is_valid_input_unit_node(unit_node: UnitNode) -> None:
        if unit_node.type != UnitNodeTypeEnum.INPUT:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST, detail=f"The output cannot be assigned a value"
            )
