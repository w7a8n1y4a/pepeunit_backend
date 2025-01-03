import uuid as uuid_pkg
from typing import Union

from fastapi import Depends

from app.configs.errors import app_errors
from app.domain.permission_model import PermissionBaseType
from app.domain.unit_model import Unit
from app.domain.unit_node_model import UnitNode
from app.repositories.enum import UserRole
from app.schemas.gql.inputs.permission import PermissionCreateInput, PermissionFilterInput
from app.schemas.pydantic.permission import PermissionCreate, PermissionFilter
from app.services.access_service import AccessService
from app.services.validators import is_valid_object, is_valid_uuid


class PermissionService:
    def __init__(
        self,
        access_service: AccessService = Depends(),
    ) -> None:
        self.access_service = access_service

    def create(self, data: Union[PermissionCreate, PermissionCreateInput]) -> PermissionBaseType:
        is_valid_uuid(data.agent_uuid)
        is_valid_uuid(data.resource_uuid)
        self.access_service.access_check([UserRole.USER, UserRole.ADMIN])

        new_permission = PermissionBaseType(**data.dict())

        self.access_service.permission_repository.is_valid_agent_type(new_permission)
        self.access_service.permission_repository.is_valid_resource_type(new_permission)

        resource = self.access_service.permission_repository.get_resource(new_permission)
        is_valid_object(resource)

        self.access_service.access_creator_check(resource)

        agent = self.access_service.permission_repository.get_agent(new_permission)
        is_valid_object(agent)

        if self.access_service.permission_repository.check(new_permission):
            app_errors.permission_error.raise_exception('Permission is exist')

        return self.access_service.permission_repository.create(new_permission)

    def get_resource_agents(
        self, filters: Union[PermissionFilter, PermissionFilterInput]
    ) -> tuple[int, list[PermissionBaseType]]:
        is_valid_uuid(filters.resource_uuid)

        self.access_service.access_check([UserRole.USER, UserRole.ADMIN])

        resource_entity = self.access_service.permission_repository.get_resource(
            PermissionBaseType(resource_uuid=filters.resource_uuid, resource_type=filters.resource_type)
        )

        is_valid_object(resource_entity)

        self.access_service.access_creator_check(resource_entity)

        return self.access_service.permission_repository.get_resource_agents(filters)

    def delete(self, agent_uuid: uuid_pkg.UUID, resource_uuid: uuid_pkg.UUID) -> None:
        self.access_service.access_check([UserRole.USER, UserRole.ADMIN])

        permission = self.access_service.permission_repository.get_by_uuid(
            agent_uuid=agent_uuid, resource_uuid=resource_uuid
        )
        is_valid_object(permission)

        base_permission = self.access_service.permission_repository.domain_to_base_type(permission)
        agent = self.access_service.permission_repository.get_agent(base_permission)
        resource = self.access_service.permission_repository.get_resource(base_permission)

        # available delete permission - creator and resource agent
        if self.access_service.current_agent.uuid != agent.uuid:
            self.access_service.access_creator_check(resource)

        if agent.uuid == resource.uuid:
            app_errors.permission_error.raise_exception('A resource\'s access to itself cannot be removed')

        if agent.uuid == resource.creator_uuid:
            app_errors.permission_error.raise_exception(
                'The creator of the resource cannot remove his access to the resource'
            )

        if isinstance(agent, Unit) and isinstance(resource, UnitNode) and resource.unit_uuid == agent.uuid:
            app_errors.permission_error.raise_exception('You cannot remove a Unit\'s access to its child UnitNodes')

        return self.access_service.permission_repository.delete(permission)
