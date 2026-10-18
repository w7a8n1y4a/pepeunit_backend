import asyncio
import random

import pytest

from app import runtime, settings
from app.domain.user_model import User
from app.dto.enum import UserRole
from app.repositories.user_repository import UserRepository
from app.schemas.pydantic.user import UserCreate
from tests.integration.helpers.keys import (
    ADMIN_USER_KEY,
    REGULAR_USER_KEY,
    UserKey,
    fresh_key,
)
from tests.integration.helpers.names import entity_name, unique_name
from tests.integration.helpers.services import token_for, user_service


def _create_user(database, cc, login: str, key: UserKey) -> User:
    user = user_service(database, cc, None).create(
        UserCreate(public_key=key.public_key)
    )
    user.login = login
    user._test_key = key
    stored = UserRepository(db=database).update(user.uuid, user)
    stored._test_key = key
    return stored


def telegram_chat_id(*, configured: bool = False) -> str:
    """Chat id of the data pipe recipient, random when the setting is empty"""
    value = settings.pu_test_integration_telegram_chat_id.strip()
    if configured and value:
        return value
    return str(random.randint(1_000_000, 10_000_000))


def _maybe_verify(
    database, cc, token: str, *, configured: bool = False
) -> None:
    if not runtime.get().pu_ff_telegram_bot_enable:
        return

    async def _verify() -> None:
        service = user_service(database, cc, token)
        link = await service.generate_verification_link()
        code = link.replace(f"{runtime.get().pu_telegram_bot_link}?start=", "")
        await service.verification(
            telegram_chat_id(configured=configured), code
        )

    asyncio.run(_verify())


@pytest.fixture(scope="session")
def regular_user(clean_leftovers, database, cc) -> User:
    user = _create_user(database, cc, entity_name("regular"), REGULAR_USER_KEY)
    user.role = UserRole.USER
    stored = UserRepository(db=database).update(user.uuid, user)
    stored._test_key = REGULAR_USER_KEY
    return stored


@pytest.fixture(scope="session")
def regular_user_token(database, cc, regular_user) -> str:
    token = token_for(database, cc, regular_user._test_key)
    _maybe_verify(database, cc, token, configured=True)
    return token


@pytest.fixture(scope="session")
def admin_user(database, cc, regular_user) -> User:
    user = _create_user(database, cc, entity_name("admin"), ADMIN_USER_KEY)
    user.role = UserRole.ADMIN
    stored = UserRepository(db=database).update(user.uuid, user)
    stored._test_key = ADMIN_USER_KEY
    return stored


@pytest.fixture(scope="session")
def admin_user_token(database, cc, admin_user) -> str:
    token = token_for(database, cc, admin_user._test_key)
    _maybe_verify(database, cc, token)
    return token


@pytest.fixture
def extra_user(database, cc) -> User:
    user = _create_user(database, cc, unique_name("extra"), fresh_key())
    yield user
    UserRepository(db=database).delete(User(uuid=user.uuid))


@pytest.fixture
def extra_user_token(database, cc, extra_user) -> str:
    return token_for(database, cc, extra_user._test_key)
