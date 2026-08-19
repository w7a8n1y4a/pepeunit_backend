import logging
import random

import pytest

from app import settings
from app.configs.errors import NoAccessError, UserError, ValidationError
from app.configs.redis import get_redis_session
from app.domain.user_model import User
from app.dto.enum import UserRole, UserStatus
from app.repositories.user_repository import UserRepository
from app.schemas.pydantic.user import UserAuth, UserCreate, UserFilter, UserUpdate
from tests.integration.helpers.names import REGULAR_USER_PASSWORD
from tests.integration.helpers.services import user_service


def test_create_user(regular_user, admin_user) -> None:
    logging.info(regular_user.login)
    logging.info(admin_user.login)
    assert regular_user.login
    assert admin_user.role == UserRole.ADMIN


def test_create_user_duplicate(database, cc, regular_user) -> None:
    service = user_service(database, cc, None)
    with pytest.raises(UserError):
        service.create(
            UserCreate(login=regular_user.login, password=REGULAR_USER_PASSWORD)
        )


def test_get_auth_token_user(regular_user_token, admin_user_token) -> None:
    assert regular_user_token
    assert admin_user_token


def test_get_auth_token_invalid_password(database, cc, regular_user) -> None:
    service = user_service(database, cc, None)
    with pytest.raises(NoAccessError):
        service.get_token(
            UserAuth(credentials=regular_user.login, password="invalid password")
        )


def test_get_auth_token_invalid_login(database, cc, admin_user) -> None:
    service = user_service(database, cc, None)
    with pytest.raises(ValidationError):
        service.get_token(
            UserAuth(credentials=admin_user.login + "invalid", password="testtest1")
        )


@pytest.mark.telegram
async def test_verification_invalid_code(
    database, cc, regular_user, regular_user_token
) -> None:
    service = user_service(database, cc, regular_user_token)
    with pytest.raises(ValidationError):
        link = await service.generate_verification_link()
        code = link.replace(f"{settings.pu_telegram_bot_link}?start=", "")
        await service.verification(str(1_000_000), code[:-2])


@pytest.mark.telegram
async def test_verification_user(
    database, cc, regular_user, regular_user_token
) -> None:
    service = user_service(database, cc, regular_user_token)
    logging.info(regular_user.uuid)

    link = await service.generate_verification_link()
    code = link.replace(f"{settings.pu_telegram_bot_link}?start=", "")
    logging.info(code)

    await service.verification(str(random.randint(1_000_000, 10_000_000)), code)

    redis = await anext(get_redis_session())
    assert await redis.get(code) is None


def test_block_unblock_user(
    database, cc, admin_user, admin_user_token, regular_user
) -> None:
    service = user_service(database, cc, admin_user_token)
    repository = UserRepository(db=database)

    for user in (regular_user, admin_user):
        logging.info(user.uuid)
        service.block(user.uuid)
        assert repository.get(User(uuid=user.uuid)).status == UserStatus.BLOCKED

        service.unblock(user.uuid)
        refreshed = repository.get(User(uuid=user.uuid))
        expected = (
            UserStatus.VERIFIED if refreshed.telegram_chat_id else UserStatus.UNVERIFIED
        )
        assert refreshed.status == expected


def test_block_without_admin(database, cc, regular_user, regular_user_token) -> None:
    service = user_service(database, cc, regular_user_token)
    with pytest.raises(NoAccessError):
        service.block(regular_user.uuid)


def test_unblock_without_admin(database, cc, regular_user, regular_user_token) -> None:
    service = user_service(database, cc, regular_user_token)
    with pytest.raises(NoAccessError):
        service.unblock(regular_user.uuid)


def test_update_user_login(database, cc, extra_user) -> None:
    token = user_service(database, cc, None).get_token(
        UserAuth(credentials=extra_user.login, password=extra_user._test_password)
    )
    service = user_service(database, cc, token)
    new_login = extra_user.login[:-1] + "x"
    service.update(UserUpdate(login=new_login))
    extra_user.login = new_login
    logging.info(new_login)


def test_update_user_login_exists(
    database, cc, extra_user, regular_user, admin_user_token
) -> None:
    token = user_service(database, cc, None).get_token(
        UserAuth(credentials=extra_user.login, password=extra_user._test_password)
    )
    service = user_service(database, cc, token)
    with pytest.raises(UserError):
        service.update(UserUpdate(login=regular_user.login))


def test_update_user_password(database, cc, extra_user) -> None:
    token = user_service(database, cc, None).get_token(
        UserAuth(credentials=extra_user.login, password=extra_user._test_password)
    )
    service = user_service(database, cc, token)
    service.update(UserUpdate(password="password"))


def test_get_many_user(database, cc, admin_user_token, test_hash, regular_user) -> None:
    service = user_service(database, cc, admin_user_token)
    count, users = service.list(
        UserFilter(
            search_string=test_hash,
            role=[UserRole.USER],
            offset=0,
            limit=settings.pu_max_pagination_size,
        )
    )
    assert any(user.uuid == regular_user.uuid for user in users)
    assert count >= 1
