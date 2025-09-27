import uuid
from unittest.mock import MagicMock

import pytest

from app.configs.errors import NoAccessError
from app.domain.unit_model import Unit
from app.domain.unit_node_model import UnitNode
from app.dto.agent.abc import Agent
from app.dto.enum import (
    AgentType,
    OwnershipType,
    PermissionEntities,
    UserRole,
    VisibilityLevel,
)
from app.repositories.permission_repository import PermissionRepository
from app.services.auth.authorization_service import AuthorizationService


@pytest.fixture
def mock_permission_repo():
    return MagicMock(spec=PermissionRepository)


@pytest.fixture
def mock_agent():
    return MagicMock(spec=Agent)


@pytest.fixture
def authorization_service(mock_permission_repo, mock_agent):
    return AuthorizationService(mock_permission_repo, mock_agent)


def test_check_access_allowed_agent_type(authorization_service, mock_agent):
    mock_agent.type = AgentType.USER
    mock_agent.role = UserRole.USER
    authorization_service.check_access([AgentType.USER])


def test_check_access_disallowed_agent_type(authorization_service, mock_agent):
    mock_agent.type = AgentType.BOT
    with pytest.raises(NoAccessError):
        authorization_service.check_access([AgentType.USER])


def test_check_access_allowed_role(authorization_service, mock_agent):
    mock_agent.type = AgentType.USER
    mock_agent.role = UserRole.ADMIN
    authorization_service.check_access([AgentType.USER], [UserRole.ADMIN])


def test_check_access_disallowed_role(authorization_service, mock_agent):
    mock_agent.type = AgentType.USER
    mock_agent.role = UserRole.USER
    with pytest.raises(NoAccessError):
        authorization_service.check_access([AgentType.USER], [UserRole.ADMIN])


def test_check_ownership_creator(authorization_service, mock_agent):
    mock_agent.type = AgentType.USER
    mock_agent.uuid = uuid.uuid4()
    entity = MagicMock()
    entity.creator_uuid = mock_agent.uuid
    authorization_service.check_ownership(entity, [OwnershipType.CREATOR])


def test_check_ownership_not_creator(authorization_service, mock_agent):
    mock_agent.type = AgentType.USER
    mock_agent.uuid = uuid.uuid4()
    entity = MagicMock()
    entity.creator_uuid = uuid.uuid4()
    with pytest.raises(NoAccessError):
        authorization_service.check_ownership(entity, [OwnershipType.CREATOR])


def test_check_ownership_unit(authorization_service, mock_agent):
    mock_agent.type = AgentType.UNIT
    mock_agent.uuid = uuid.uuid4()
    entity = MagicMock(spec=Unit)
    entity.uuid = mock_agent.uuid
    authorization_service.check_ownership(entity, [OwnershipType.UNIT])


def test_check_ownership_not_unit(authorization_service, mock_agent):
    mock_agent.type = AgentType.UNIT
    mock_agent.uuid = uuid.uuid4()
    mock_agent.name = "test"
    entity = MagicMock(spec=Unit)
    entity.uuid = uuid.uuid4()
    with pytest.raises(NoAccessError):
        authorization_service.check_ownership(entity, [OwnershipType.UNIT])


def test_check_ownership_unit_to_input_node(authorization_service, mock_agent):
    mock_agent.type = AgentType.UNIT
    entity = MagicMock(spec=UnitNode)
    entity.is_rewritable_input = True
    authorization_service.check_ownership(entity, [OwnershipType.UNIT_TO_INPUT_NODE])


def test_check_ownership_not_unit_to_input_node(authorization_service, mock_agent):
    mock_agent.type = AgentType.UNIT
    entity = MagicMock(spec=UnitNode)
    entity.is_rewritable_input = False
    with pytest.raises(NoAccessError):
        authorization_service.check_ownership(
            entity, [OwnershipType.UNIT_TO_INPUT_NODE]
        )


def test_check_visibility_public(authorization_service, mock_agent):
    mock_agent.type = AgentType.USER
    entity = MagicMock()
    entity.visibility_level = VisibilityLevel.PUBLIC
    authorization_service.check_visibility(entity)


def test_check_visibility_internal_allowed(authorization_service, mock_agent):
    mock_agent.type = AgentType.USER
    entity = MagicMock()
    entity.visibility_level = VisibilityLevel.INTERNAL
    authorization_service.check_visibility(entity)


def test_check_visibility_internal_disallowed(authorization_service, mock_agent):
    mock_agent.type = AgentType.BOT
    entity = MagicMock()
    entity.visibility_level = VisibilityLevel.INTERNAL
    with pytest.raises(NoAccessError):
        authorization_service.check_visibility(entity)


def test_check_visibility_private_allowed(
    authorization_service, mock_agent, mock_permission_repo
):
    mock_agent.type = AgentType.USER
    mock_agent.uuid = uuid.uuid4()
    entity = MagicMock()
    entity.visibility_level = VisibilityLevel.PRIVATE
    entity.uuid = uuid.uuid4()
    entity.__class__.__name__ = "Unit"
    mock_permission_repo.check.return_value = True
    authorization_service.check_visibility(entity)


def test_check_visibility_private_disallowed(
    authorization_service, mock_agent, mock_permission_repo
):
    mock_agent.type = AgentType.USER
    mock_agent.uuid = uuid.uuid4()
    entity = MagicMock()
    entity.visibility_level = VisibilityLevel.PRIVATE
    entity.uuid = uuid.uuid4()
    entity.__class__.__name__ = "Unit"
    mock_permission_repo.check.return_value = False
    with pytest.raises(NoAccessError):
        authorization_service.check_visibility(entity)


def test_access_restriction(authorization_service, mock_permission_repo, mock_agent):
    mock_agent.type = AgentType.USER
    mock_agent.uuid = uuid.uuid4()

    mock_permission_repo.get_agent_resources.return_value = [
        MagicMock(resource_uuid=uuid.uuid4()),
        MagicMock(resource_uuid=uuid.uuid4()),
    ]
    result = authorization_service.access_restriction(PermissionEntities.UNIT)
    assert len(result) == 2


def test_get_available_visibility_levels_bot(authorization_service, mock_agent):
    mock_agent.type = AgentType.BOT
    result = authorization_service.get_available_visibility_levels(
        ["PUBLIC", "INTERNAL"]
    )
    assert result == [VisibilityLevel.PUBLIC]


def test_get_available_visibility_levels_user_with_restriction(
    authorization_service, mock_agent
):
    mock_agent.type = AgentType.USER
    result = authorization_service.get_available_visibility_levels(
        ["PUBLIC", "INTERNAL"], ["INTERNAL"]
    )
    assert result == ["PUBLIC", "INTERNAL"]


def test_get_available_visibility_levels_user_without_restriction(
    authorization_service, mock_agent
):
    mock_agent.type = AgentType.USER
    result = authorization_service.get_available_visibility_levels(
        ["PUBLIC", "INTERNAL"]
    )
    assert result == [VisibilityLevel.PUBLIC, VisibilityLevel.INTERNAL]
