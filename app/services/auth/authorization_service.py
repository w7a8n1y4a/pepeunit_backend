import uuid as uuid_pkg

from app.configs.errors import NoAccessError
from app.domain.permission_model import PermissionBaseType
from app.domain.repository_registry_model import RepositoryRegistry
from app.domain.unit_model import Unit
from app.domain.unit_node_model import UnitNode
from app.dto.agent.abc import Agent
from app.dto.enum import (
    AgentType,
    CredentialStatus,
    OwnershipType,
    PermissionEntities,
    UserRole,
    VisibilityLevel,
)
from app.repositories.permission_repository import PermissionRepository


class AuthorizationService:
    def __init__(
        self, permission_repo: PermissionRepository, current_agent: Agent
    ):
        self.permission_repo = permission_repo
        self.current_agent = current_agent

    def check_access(
        self,
        allowed_agent_types: list[AgentType],
        allowed_roles: list[UserRole] = (UserRole.USER, UserRole.ADMIN),
    ) -> None:
        if self.current_agent.type not in allowed_agent_types:
            msg = f"{self.current_agent.__class__.__name__} access not allowed, only for {allowed_agent_types}"
            raise NoAccessError(msg)

        if (
            self.current_agent.type == AgentType.USER
            and self.current_agent.role not in allowed_roles
        ):
            msg = f"{self.current_agent.__class__.__name__} access not allowed, only for {allowed_roles}"
            raise NoAccessError(msg)

    def check_ownership(
        self, entity, ownership_types: list[OwnershipType]
    ) -> None:
        if (
            OwnershipType.CREATOR in ownership_types
            and self.current_agent.type == AgentType.USER
            and self.current_agent.uuid != entity.creator_uuid
        ):
            msg = f"{self.current_agent.__class__.__name__} is not creator this entity - {entity.__class__.__name__}."
            raise NoAccessError(msg)
        if (
            OwnershipType.UNIT in ownership_types
            and self.current_agent.type == AgentType.UNIT
            and isinstance(entity, Unit)
            and entity.uuid != self.current_agent.uuid
        ):
            msg = f"The Unit {self.current_agent.name} requesting the information does not have access to it"
            raise NoAccessError(msg)

        if (
            OwnershipType.UNIT_TO_INPUT_NODE in ownership_types
            and self.current_agent.type == AgentType.UNIT
            and isinstance(entity, UnitNode)
            and not entity.is_rewritable_input
        ):
            msg = "The Unit requesting the information does not have access to it"
            raise NoAccessError(msg)

    def check_visibility(self, check_entity):
        if isinstance(check_entity, RepositoryRegistry):
            if not check_entity.is_public_repository:
                if self.current_agent.type in [AgentType.BOT]:
                    msg = "Private RepositoryRegistry is not allowed"
                    raise NoAccessError(msg)
                if self.current_agent.type == [
                    AgentType.BACKEND,
                    AgentType.USER,
                    AgentType.UNIT,
                ]:
                    return
            return

        if (
            self.current_agent.type == AgentType.BACKEND
            or check_entity.visibility_level == VisibilityLevel.PUBLIC
        ):
            pass
        elif check_entity.visibility_level == VisibilityLevel.INTERNAL:
            if self.current_agent.type not in [AgentType.USER, AgentType.UNIT]:
                msg = "Internal visibility level is not allowed"
                raise NoAccessError(msg)
        elif check_entity.visibility_level == VisibilityLevel.PRIVATE:
            permission_check = PermissionBaseType(
                agent_type=self.current_agent.type,
                agent_uuid=self.current_agent.uuid,
                resource_type=check_entity.__class__.__name__,
                resource_uuid=check_entity.uuid,
            )
            if not self.permission_repo.check(permission_check):
                msg = "Private visibility level is not allowed"
                raise NoAccessError(msg)

    def check_repository_registry_access(self, check_entity):
        if not isinstance(check_entity, RepositoryRegistry):
            msg = "Only RepositoryRegistry entity"
            raise NoAccessError(msg)

        if self.current_agent.type is not AgentType.USER:
            msg = "RepositoryRegistry operation allowed only for Users"
            raise NoAccessError(msg)

        if not check_entity.is_public_repository:
            all_credentials_with_status = check_entity.get_credentials()
            if not all_credentials_with_status:
                msg = "This RepositoryRegistry has no Credentials"
                raise NoAccessError(msg)

            current_user_credentials = check_entity.get_credentials_by_user(
                all_credentials_with_status, str(self.current_agent.uuid)
            )

            if not current_user_credentials:
                msg = "This User has no external Platform Credentials for operation with RepositoryRegistry"
                raise NoAccessError(msg)

            if current_user_credentials.status != CredentialStatus.VALID:
                msg = f"Status Credentials external Platform: {current_user_credentials.status}"
                raise NoAccessError(msg)

    def access_restriction(
        self, resource_type: PermissionEntities | None = None
    ) -> list[uuid_pkg]:
        return [
            item.resource_uuid
            for item in self.permission_repo.get_agent_resources(
                PermissionBaseType(
                    agent_type=AgentType.USER
                    if self.current_agent.type == AgentType.BOT
                    else self.current_agent.type,
                    agent_uuid=self.current_agent.uuid,
                    resource_type=resource_type,
                )
            )
        ]

    def get_available_visibility_levels(
        self, levels: list[str], restriction: list[str] = None
    ) -> list[VisibilityLevel]:
        if self.current_agent.type == AgentType.BOT:
            return [VisibilityLevel.PUBLIC]
        if restriction:
            return levels
        return [VisibilityLevel.PUBLIC, VisibilityLevel.INTERNAL]
