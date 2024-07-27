from typing import Union
import uuid as uuid_pkg

from fastapi import Depends
from fastapi import HTTPException
from fastapi import status as http_status

from app.domain.permission_model import Permission, PermissionBaseType
from app.domain.unit_model import Unit
from app.repositories.enum import UserRole
from app.schemas.gql.inputs.permission import PermissionCreateInput, ResourceInput
from app.schemas.pydantic.permission import PermissionCreate, Resource, PermissionRead
from app.services.access_service import AccessService
from app.services.utils import creator_check
from app.services.validators import is_valid_object


class PermissionService:
    def __init__(
        self,
        access_service: AccessService = Depends(),
    ) -> None:
        self.access_service = access_service

    def create(self, data: Union[PermissionCreate, PermissionCreateInput]) -> PermissionBaseType:
        self.access_service.access_check([UserRole.USER, UserRole.ADMIN])

        new_permission = PermissionBaseType(**data.dict())

        resource = self.access_service.permission_repository.get_resource(new_permission)
        is_valid_object(resource)

        creator_check(self.access_service.current_agent, resource)

        agent = self.access_service.permission_repository.get_agent(new_permission)
        is_valid_object(agent)

        if self.access_service.permission_repository.check(new_permission):
            raise HTTPException(status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Permission is exist")

        self.access_service.permission_repository.is_valid_agent_type(new_permission)
        self.access_service.permission_repository.is_valid_resource_type(new_permission)

        return self.access_service.permission_repository.create(new_permission)

    def get_resource_agents(self, resource: Union[Resource, ResourceInput]) -> list[PermissionBaseType]:
        self.access_service.access_check([UserRole.USER, UserRole.ADMIN])

        resource_entity = self.access_service.permission_repository.get_resource(
            PermissionBaseType(
                resource_uuid=resource.resource_uuid,
                resource_type=resource.resource_type
            )
        )

        is_valid_object(resource_entity)

        creator_check(self.access_service.current_agent, resource_entity)

        return self.access_service.permission_repository.get_resource_agents(
            PermissionBaseType(
                resource_uuid=resource.resource_uuid,
                resource_type=resource.resource_type
            )
        )

    def delete(self, uuid: uuid_pkg.UUID) -> None:
        self.access_service.access_check([UserRole.USER, UserRole.ADMIN])

        permission = self.access_service.permission_repository.get(Permission(uuid=uuid))
        is_valid_object(permission)

        # available delete permission - creator and resource agent
        if not permission.agent_uuid == self.access_service.current_agent.uuid:
            resource = self.access_service.permission_repository.get_resource(permission)
            creator_check(self.access_service.current_agent, resource)

        return self.access_service.permission_repository.delete(permission)
