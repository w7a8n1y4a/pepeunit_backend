import asyncio
import random

import pytest

from app import settings
from app.domain.user_model import User
from app.dto.enum import UserRole
from app.repositories.user_repository import UserRepository
from app.schemas.pydantic.user import UserAuth, UserCreate
from tests.integration.helpers.names import (
    ADMIN_USER_PASSWORD,
    REGULAR_USER_PASSWORD,
    entity_name,
    unique_name,
)
from tests.integration.helpers.services import user_service


def _create_user(database, cc, login: str, password: str) -> User:
    return user_service(database, cc, None).create(
        UserCreate(login=login, password=password)
    )


def _token_for(database, cc, login: str, password: str) -> str:
    return user_service(database, cc, None).get_token(
        UserAuth(credentials=login, password=password)
    )


def _maybe_verify(database, cc, token: str) -> None:
    if not settings.pu_ff_telegram_bot_enable:
        return

    async def _verify() -> None:
        service = user_service(database, cc, token)
        link = await service.generate_verification_link()
        code = link.replace(f"{settings.pu_telegram_bot_link}?start=", "")
        await service.verification(str(random.randint(1_000_000, 10_000_000)), code)

    asyncio.run(_verify())


@pytest.fixture(scope="session")
def regular_user(clean_leftovers, database, cc) -> User:
    user = _create_user(
        database, cc, entity_name("regular"), REGULAR_USER_PASSWORD
    )
    user.role = UserRole.USER
    return UserRepository(db=database).update(user.uuid, user)


@pytest.fixture(scope="session")
def regular_user_token(database, cc, regular_user) -> str:
    token = _token_for(database, cc, regular_user.login, REGULAR_USER_PASSWORD)
    _maybe_verify(database, cc, token)
    return token


@pytest.fixture(scope="session")
def admin_user(database, cc, regular_user) -> User:
    user = _create_user(database, cc, entity_name("admin"), ADMIN_USER_PASSWORD)
    user.role = UserRole.ADMIN
    return UserRepository(db=database).update(user.uuid, user)


@pytest.fixture(scope="session")
def admin_user_token(database, cc, admin_user) -> str:
    token = _token_for(database, cc, admin_user.login, ADMIN_USER_PASSWORD)
    _maybe_verify(database, cc, token)
    return token


@pytest.fixture
def extra_user(database, cc) -> User:
    login = unique_name("extra")
    password = "testtestx"
    user = _create_user(database, cc, login, password)
    user._test_password = password
    yield user
    UserRepository(db=database).delete(User(uuid=user.uuid))


@pytest.fixture
def extra_user_token(database, cc, extra_user) -> str:
    return _token_for(database, cc, extra_user.login, extra_user._test_password)
