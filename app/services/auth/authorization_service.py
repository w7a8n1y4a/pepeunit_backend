import uuid as uuid_pkg

from app.configs.error_codes import ErrorCode
from app.configs.errors import NoAccessError
from app.domain.permission_model import PermissionBaseType
from app.domain.repo_model import Repo
from app.domain.unit_io_model import UnitIO
from app.domain.unit_model import Unit
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
        allowed_roles: list[UserRole] = (
            UserRole.USER,
            UserRole.ADMIN,
            UserRole.OWNER,
        ),
    ) -> None:
        if self.current_agent.type not in allowed_agent_types:
            msg = f"{self.current_agent.__class__.__name__} access not allowed, only for {allowed_agent_types}"
            raise NoAccessError(
                msg, code=ErrorCode.ACCESS_AGENT_TYPE_NOT_ALLOWED
            )

        if (
            self.current_agent.type == AgentType.USER
            and not self._role_is_allowed(allowed_roles)
        ):
            msg = f"{self.current_agent.__class__.__name__} access not allowed, only for {allowed_roles}"
            raise NoAccessError(msg, code=ErrorCode.ACCESS_ROLE_NOT_ALLOWED)

    def _role_is_allowed(self, allowed_roles: list[UserRole]) -> bool:
        order = (UserRole.USER, UserRole.ADMIN, UserRole.OWNER)
        try:
            level = order.index(self.current_agent.role)
        except ValueError:
            return False

        required = [
            order.index(role) for role in allowed_roles if role in order
        ]
        if not required:
            return False
        return level >= min(required)

    def check_ownership(
        self, entity, ownership_types: list[OwnershipType]
    ) -> None:
        if (
            OwnershipType.CREATOR in ownership_types
            and self.current_agent.type == AgentType.USER
            and self.current_agent.uuid != entity.creator_uuid
        ):
            msg = f"{self.current_agent.__class__.__name__} is not creator this entity - {entity.__class__.__name__}."
            raise NoAccessError(msg, code=ErrorCode.ACCESS_NOT_CREATOR)
        if (
            OwnershipType.UNIT in ownership_types
            and self.current_agent.type == AgentType.UNIT
            and isinstance(entity, Unit)
            and entity.uuid != self.current_agent.uuid
        ):
            msg = f"The Unit {self.current_agent.name} requesting the information does not have access to it"
            raise NoAccessError(msg, code=ErrorCode.ACCESS_UNIT_REQUEST_DENIED)

        if (
            OwnershipType.UNIT_TO_INPUT_NODE in ownership_types
            and self.current_agent.type == AgentType.UNIT
            and isinstance(entity, UnitIO)
            and not entity.is_rewritable_input
        ):
            msg = "The Unit requesting the information does not have access to it"
            raise NoAccessError(msg, code=ErrorCode.ACCESS_UNIT_INPUT_DENIED)

    def _require_user_or_unit(self, level: str) -> None:
        if self.current_agent.type not in (AgentType.USER, AgentType.UNIT):
            msg = f"{level} visibility level is not allowed"
            raise NoAccessError(
                msg, code=ErrorCode.ACCESS_VISIBILITY_LEVEL_NOT_ALLOWED
            )

    def _check_repo_visibility(self, check_entity) -> None:
        if (
            not check_entity.is_public_repository
            and self.current_agent.type == AgentType.BOT
        ):
            msg = "Private Repo is not allowed"
            raise NoAccessError(msg, code=ErrorCode.ACCESS_PRIVATE_REPO)

    def check_visibility(self, check_entity):
        if isinstance(check_entity, Repo):
            self._check_repo_visibility(check_entity)
            return

        if (
            self.current_agent.type == AgentType.BACKEND
            or check_entity.visibility_level == VisibilityLevel.PUBLIC
        ):
            return

        if check_entity.visibility_level == VisibilityLevel.INTERNAL:
            self._require_user_or_unit("Internal")
            return

        if check_entity.visibility_level == VisibilityLevel.PRIVATE:
            self._require_user_or_unit("Private")
            permission_check = PermissionBaseType(
                agent_type=self.current_agent.type,
                agent_uuid=self.current_agent.uuid,
                resource_type=check_entity.__class__.__name__,
                resource_uuid=check_entity.uuid,
            )
            if not self.permission_repo.check(permission_check):
                msg = "Private visibility level is not allowed"
                raise NoAccessError(
                    msg, code=ErrorCode.ACCESS_PRIVATE_VISIBILITY
                )

    def check_repo_access(self, check_entity):
        if not isinstance(check_entity, Repo):
            msg = "Only Repo entity"
            raise NoAccessError(msg, code=ErrorCode.ACCESS_REPO_ONLY)

        if self.current_agent.type is not AgentType.USER:
            msg = "Repo operation allowed only for Users"
            raise NoAccessError(msg, code=ErrorCode.ACCESS_REPO_USERS_ONLY)

        if not check_entity.is_public_repository:
            all_credentials_with_status = check_entity.get_credentials()
            if not all_credentials_with_status:
                msg = "This Repo has no Credentials"
                raise NoAccessError(
                    msg,
                    code=ErrorCode.ACCESS_REPO_NO_CREDENTIALS,
                )

            current_user_credentials = check_entity.get_credentials_by_user(
                all_credentials_with_status, str(self.current_agent.uuid)
            )

            if not current_user_credentials:
                msg = "This User has no external Platform Credentials for operation with Repo"
                raise NoAccessError(
                    msg, code=ErrorCode.ACCESS_NO_PLATFORM_CREDENTIALS
                )

            if current_user_credentials.status != CredentialStatus.VALID:
                msg = f"Status Credentials external Platform: {current_user_credentials.status}"
                raise NoAccessError(
                    msg, code=ErrorCode.ACCESS_PLATFORM_CREDENTIALS_STATUS
                )

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
