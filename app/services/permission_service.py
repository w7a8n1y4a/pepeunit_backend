import uuid as uuid_pkg

from fastapi import Depends

from app.configs.error_codes import ErrorCode
from app.configs.errors import CustomPermissionError
from app.domain.permission_model import PermissionBaseType
from app.domain.unit_io_model import UnitIO
from app.domain.unit_model import Unit
from app.domain.user_model import User
from app.dto.enum import AgentType, NotFoundEntity, OwnershipType, UuidEntity
from app.repositories.permission_repository import PermissionRepository
from app.schemas.pydantic.permission import PermissionCreate, PermissionFilter
from app.services.access_service import AccessService
from app.services.validators import is_valid_object, is_valid_uuid


class PermissionService:
    def __init__(
        self,
        access_service: AccessService = Depends(),
        permission_repository: PermissionRepository = Depends(),
    ) -> None:
        self.access_service = access_service
        self.permission_repository = permission_repository

    def create(
        self,
        data: PermissionCreate | PermissionBaseType,
        is_api: bool = True,
    ) -> PermissionBaseType:
        is_valid_uuid(data.agent_uuid, UuidEntity.PERMISSION_AGENT)
        is_valid_uuid(data.resource_uuid, UuidEntity.PERMISSION_RESOURCE)

        if is_api:
            self.access_service.authorization.check_access([AgentType.USER])

        new_permission = PermissionBaseType(**data.dict())

        self.permission_repository.is_valid_agent_type(new_permission)
        self.permission_repository.is_valid_resource_type(new_permission)

        resource = self.permission_repository.get_resource(new_permission)
        is_valid_object(resource, NotFoundEntity(new_permission.resource_type))

        if is_api:
            self.access_service.authorization.check_ownership(
                resource, [[OwnershipType.CREATOR]]
            )

        agent = self.permission_repository.get_agent(new_permission)
        is_valid_object(agent, NotFoundEntity(new_permission.agent_type))

        if self.permission_repository.check(new_permission):
            msg = "Permission is exist"
            raise CustomPermissionError(msg, code=ErrorCode.PERMISSION_EXISTS)

        return self.permission_repository.create(new_permission)

    def create_by_domains(
        self, agent: User | Unit, resource: Unit | UnitIO
    ) -> PermissionBaseType:
        agent_type = agent.__class__.__name__
        resource_type = resource.__class__.__name__

        new_permission = PermissionBaseType(
            agent_uuid=agent.uuid,
            agent_type=agent_type,
            resource_uuid=resource.uuid,
            resource_type=resource_type,
        )

        return self.create(new_permission, is_api=False)

    def get_resource_agents(
        self, filters: PermissionFilter
    ) -> tuple[int, list[PermissionBaseType]]:
        is_valid_uuid(filters.resource_uuid, UuidEntity.PERMISSION_RESOURCE)

        self.access_service.authorization.check_access([AgentType.USER])

        resource_entity = self.permission_repository.get_resource(
            PermissionBaseType(
                resource_uuid=filters.resource_uuid,
                resource_type=filters.resource_type,
            )
        )

        is_valid_object(resource_entity, NotFoundEntity(filters.resource_type))

        self.access_service.authorization.check_ownership(
            resource_entity, [[OwnershipType.CREATOR]]
        )

        return self.permission_repository.get_resource_agents(filters)

    def delete(
        self,
        agent_uuid: uuid_pkg.UUID,
        resource_uuid: uuid_pkg.UUID,
        is_api: bool = True,
    ) -> None:
        if is_api:
            self.access_service.authorization.check_access([AgentType.USER])

        permission = self.permission_repository.get_by_uuid(
            agent_uuid=agent_uuid, resource_uuid=resource_uuid
        )
        is_valid_object(permission, NotFoundEntity.PERMISSION)

        base_permission = self.permission_repository.domain_to_base_type(
            permission
        )
        agent = self.permission_repository.get_agent(base_permission)
        resource = self.permission_repository.get_resource(base_permission)

        # available delete permission - creator and resource agent
        if is_api and self.access_service.current_agent.uuid != agent.uuid:
            self.access_service.authorization.check_ownership(
                resource, [[OwnershipType.CREATOR]]
            )

        if agent.uuid == resource.uuid:
            msg = "A resource's access to itself cannot be removed"
            raise CustomPermissionError(
                msg, code=ErrorCode.PERMISSION_SELF_ACCESS
            )

        if agent.uuid == resource.creator_uuid:
            msg = "The creator of the resource cannot remove his access to the resource"
            raise CustomPermissionError(
                msg, code=ErrorCode.PERMISSION_CREATOR_ACCESS
            )

        if (
            isinstance(agent, Unit)
            and isinstance(resource, UnitIO)
            and resource.unit_uuid == agent.uuid
        ):
            msg = "You cannot remove a Unit's access to its child UnitIOs"
            raise CustomPermissionError(
                msg, code=ErrorCode.PERMISSION_UNIT_CHILD_IO
            )

        return self.permission_repository.delete(permission)
