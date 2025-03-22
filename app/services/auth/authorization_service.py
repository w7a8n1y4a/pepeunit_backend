import uuid as uuid_pkg
from typing import Optional

from app.configs.errors import NoAccessError
from app.domain.permission_model import PermissionBaseType
from app.domain.unit_model import Unit
from app.domain.unit_node_model import UnitNode
from app.dto.agent.abc import Agent
from app.repositories.enum import AgentType, OwnershipType, PermissionEntities, UserRole, VisibilityLevel
from app.repositories.permission_repository import PermissionRepository


class AuthorizationService:

    def __init__(self, permission_repo: PermissionRepository, current_agent: Agent):
        self.permission_repo = permission_repo
        self.current_agent = current_agent

    def check_access(
        self, allowed_agent_types: list[AgentType], allowed_roles: list[UserRole] = (UserRole.USER, UserRole.ADMIN)
    ) -> None:
        if self.current_agent.type not in allowed_agent_types:
            raise NoAccessError(
                "{} access not allowed, only for {}".format(self.current_agent.__class__.__name__, allowed_agent_types)
            )

        if self.current_agent.type == AgentType.USER and self.current_agent.role not in allowed_roles:
            raise NoAccessError(
                "{} access not allowed, only for {}".format(self.current_agent.__class__.__name__, allowed_roles)
            )

    def check_ownership(self, entity, ownership_types: list[OwnershipType]) -> None:
        if OwnershipType.CREATOR in ownership_types and self.current_agent.type == AgentType.USER:
            if self.current_agent.uuid != entity.creator_uuid:
                raise NoAccessError(
                    "{} is not creator this entity - {}.".format(
                        self.current_agent.__class__.__name__, entity.__class__.__name__
                    )
                )
        if OwnershipType.UNIT in ownership_types and self.current_agent.type == AgentType.UNIT:
            if isinstance(entity, Unit) and entity.uuid != self.current_agent.uuid:
                raise NoAccessError(
                    "The Unit {} requesting the information does not have access to it".format(self.current_agent.name)
                )

        if OwnershipType.UNIT_TO_INPUT_NODE in ownership_types and self.current_agent.type == AgentType.UNIT:
            if isinstance(entity, UnitNode) and not entity.is_rewritable_input:
                raise NoAccessError("The Unit requesting the information does not have access to it")

    def check_visibility(self, check_entity):
        if check_entity.visibility_level == VisibilityLevel.PUBLIC:
            pass
        elif check_entity.visibility_level == VisibilityLevel.INTERNAL:
            if self.current_agent.type not in [AgentType.USER, AgentType.UNIT]:
                raise NoAccessError("Internal visibility level is not allowed")
        elif check_entity.visibility_level == VisibilityLevel.PRIVATE:
            permission_check = PermissionBaseType(
                agent_type=self.current_agent.type,
                agent_uuid=self.current_agent.uuid,
                resource_type=check_entity.__class__.__name__,
                resource_uuid=check_entity.uuid,
            )
            if not self.permission_repo.check(permission_check):
                raise NoAccessError("Private visibility level is not allowed")

    def access_restriction(self, resource_type: Optional[PermissionEntities] = None) -> list[uuid_pkg]:
        """
        Allows to get the uuid of all entities to which the agent has access
        """
        return [
            item.resource_uuid
            for item in self.permission_repo.get_agent_resources(
                PermissionBaseType(
                    agent_type=self.current_agent.type,
                    agent_uuid=self.current_agent.uuid,
                    resource_type=resource_type,
                )
            )
        ]

    def get_available_visibility_levels(
        self, levels: list[str], restriction: list[str] = None
    ) -> list[VisibilityLevel]:
        """
        Prohibits all external users from getting information about internal entities and cuts off
        Private entities if the agent does not have any records about them
        """

        if not isinstance(self.current_agent, Unit) and self.current_agent.role == UserRole.BOT:
            return [VisibilityLevel.PUBLIC]
        else:
            if restriction:
                return levels
            else:
                return [VisibilityLevel.PUBLIC, VisibilityLevel.INTERNAL]
