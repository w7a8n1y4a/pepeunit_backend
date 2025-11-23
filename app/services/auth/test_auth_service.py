import uuid as uuid_pkg
from unittest.mock import Mock

import jwt
import pytest

from app import settings
from app.configs.errors import NoAccessError
from app.domain.unit_model import Unit
from app.domain.user_model import User
from app.dto.agent.abc import AgentBackend, AgentBot, AgentUnit, AgentUser
from app.dto.enum import AgentStatus, AgentType
from app.services.auth.auth_service import JwtAuthService, TgBotAuthService


@pytest.fixture
def mock_repos():
    user_repo = Mock()
    unit_repo = Mock()
    return user_repo, unit_repo


def test_decode_user_token_success(mock_repos):
    user_repo, unit_repo = mock_repos
    user_uuid = uuid_pkg.uuid4()
    user = User(uuid=user_uuid, login="test_user", status=AgentStatus.VERIFIED)
    user_repo.get.return_value = user

    agent = AgentUser(
        uuid=user_uuid,
        name="test_user",
        type=AgentType.USER,
        status=AgentStatus.VERIFIED,
    )
    token = agent.generate_agent_token()

    auth_service = JwtAuthService(user_repo, unit_repo, token)
    current_agent = auth_service.get_current_agent()

    assert isinstance(current_agent, AgentUser)
    assert current_agent.uuid == user_uuid
    assert current_agent.name == "test_user"
    assert current_agent.status == AgentStatus.VERIFIED


def test_decode_expired_token(mock_repos):
    user_repo, unit_repo = mock_repos
    user_uuid = uuid_pkg.uuid4()
    user = User(uuid=user_uuid, login="test_user", status=AgentStatus.VERIFIED)
    user_repo.get.return_value = user

    agent = AgentUser(
        uuid=user_uuid,
        name="test_user",
        type=AgentType.USER,
        status=AgentStatus.VERIFIED,
    )
    token = agent.generate_agent_token(10000)

    with pytest.raises(NoAccessError, match="Token expired"):
        JwtAuthService(user_repo, unit_repo, token)


def test_decode_invalid_token(mock_repos):
    user_repo, unit_repo = mock_repos
    invalid_token = "invalid_token"

    with pytest.raises(NoAccessError, match="Token is invalid"):
        JwtAuthService(user_repo, unit_repo, invalid_token)


def test_user_not_found(mock_repos):
    user_repo, unit_repo = mock_repos
    user_uuid = uuid_pkg.uuid4()
    user_repo.get.return_value = None

    agent = AgentUser(
        uuid=user_uuid,
        name="test_user",
        type=AgentType.USER,
        status=AgentStatus.VERIFIED,
    )
    token = agent.generate_agent_token()

    with pytest.raises(NoAccessError, match="User not found"):
        JwtAuthService(user_repo, unit_repo, token)


def test_agent_blocked(mock_repos):
    user_repo, unit_repo = mock_repos
    user_uuid = uuid_pkg.uuid4()
    user = User(uuid=user_uuid, login="test_user", status=AgentStatus.BLOCKED)
    user_repo.get.return_value = user

    agent = AgentUser(
        uuid=user_uuid,
        name="test_user",
        type=AgentType.USER,
        status=AgentStatus.BLOCKED,
    )
    token = agent.generate_agent_token()

    with pytest.raises(NoAccessError, match="Agent is blocked or not found"):
        JwtAuthService(user_repo, unit_repo, token)


def test_decode_unit_token_success(mock_repos):
    user_repo, unit_repo = mock_repos
    unit_uuid = uuid_pkg.uuid4()
    unit = Unit(uuid=unit_uuid, name="test_unit", status=AgentStatus.VERIFIED)
    unit_repo.get.return_value = unit

    agent = AgentUnit(
        uuid=unit_uuid,
        name="test_unit",
        type=AgentType.UNIT,
        status=AgentStatus.VERIFIED,
    )
    token = agent.generate_agent_token()

    auth_service = JwtAuthService(user_repo, unit_repo, token)
    current_agent = auth_service.get_current_agent()

    assert isinstance(current_agent, AgentUnit)
    assert current_agent.uuid == unit_uuid
    assert current_agent.name == "test_unit"
    assert current_agent.status == AgentStatus.VERIFIED


def test_unit_not_found(mock_repos):
    user_repo, unit_repo = mock_repos
    unit_uuid = uuid_pkg.uuid4()
    unit_repo.get.return_value = None

    agent = AgentUnit(
        uuid=unit_uuid,
        name="test_unit",
        type=AgentType.UNIT,
        status=AgentStatus.VERIFIED,
    )
    token = agent.generate_agent_token()

    with pytest.raises(NoAccessError, match="Unit not found"):
        JwtAuthService(user_repo, unit_repo, token)


def test_decode_backend_token_success(mock_repos):
    user_repo, unit_repo = mock_repos

    agent = AgentBackend(
        name=settings.pu_domain,
        type=AgentType.BACKEND,
        status=AgentStatus.VERIFIED,
    )
    token = agent.generate_agent_token()

    auth_service = JwtAuthService(user_repo, unit_repo, token)
    current_agent = auth_service.get_current_agent()

    assert isinstance(current_agent, AgentBackend)
    assert current_agent.name == settings.pu_domain
    assert current_agent.status == AgentStatus.VERIFIED


def test_unknown_agent_type(mock_repos):
    user_repo, unit_repo = mock_repos

    token = jwt.encode(
        {"uuid": str(uuid_pkg.uuid4()), "type": "UNKNOWN_TYPE"},
        settings.pu_secret_key,
        algorithm="HS256",
    )

    with pytest.raises(NoAccessError, match="Invalid agent type"):
        JwtAuthService(user_repo, unit_repo, token)


def test_no_token_provided(mock_repos):
    user_repo, unit_repo = mock_repos
    auth_service = JwtAuthService(user_repo, unit_repo, None)
    agent = auth_service.get_current_agent()

    assert isinstance(agent, AgentBot)
    assert agent.status == AgentStatus.UNVERIFIED


def test_init_with_telegram_chat_id(mock_repos):
    user_repo, unit_repo = mock_repos
    telegram_chat_id = "12345"
    user_uuid = uuid_pkg.uuid4()
    user = User(uuid=user_uuid, login="test_user", status=AgentStatus.VERIFIED)
    user_repo.get_user_by_credentials.return_value = user

    auth_service = TgBotAuthService(user_repo, unit_repo, telegram_chat_id)

    assert auth_service.telegram_chat_id == telegram_chat_id
    assert isinstance(auth_service.current_agent, AgentUser)
    user_repo.get_user_by_credentials.assert_called_once_with(telegram_chat_id)


def test_init_without_telegram_chat_id(mock_repos):
    user_repo, unit_repo = mock_repos
    telegram_chat_id = None

    auth_service = TgBotAuthService(user_repo, unit_repo, telegram_chat_id)

    assert auth_service.telegram_chat_id is None
    assert isinstance(auth_service.current_agent, AgentBot)
    user_repo.get_user_by_credentials.assert_not_called()


def test_get_agent_by_chat_id_user_not_found(mock_repos):
    user_repo, unit_repo = mock_repos
    telegram_chat_id = "12345"
    user_repo.get_user_by_credentials.return_value = None

    with pytest.raises(NoAccessError, match="User not found"):
        TgBotAuthService(user_repo, unit_repo, telegram_chat_id)


def test_get_agent_by_chat_id_user_blocked(mock_repos):
    user_repo, unit_repo = mock_repos
    telegram_chat_id = "12345"
    user_uuid = uuid_pkg.uuid4()
    user = User(uuid=user_uuid, login="test_user", status=AgentStatus.BLOCKED)
    user_repo.get_user_by_credentials.return_value = user

    with pytest.raises(NoAccessError, match="User is Blocked"):
        TgBotAuthService(user_repo, unit_repo, telegram_chat_id)


def test_get_current_agent(mock_repos):
    user_repo, unit_repo = mock_repos
    telegram_chat_id = "12345"
    user_uuid = uuid_pkg.uuid4()
    user = User(uuid=user_uuid, login="test_user", status=AgentStatus.VERIFIED)
    user_repo.get_user_by_credentials.return_value = user
    auth_service = TgBotAuthService(user_repo, unit_repo, telegram_chat_id)

    current_agent = auth_service.get_current_agent()

    assert isinstance(current_agent, AgentUser)
    assert current_agent.status == AgentStatus.VERIFIED
