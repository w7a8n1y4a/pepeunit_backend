import logging
import uuid

import pytest

from app import settings
from app.configs.errors import NoAccessError, UserError, ValidationError
from app.configs.redis import get_redis_session
from app.domain.user_model import User
from app.dto.enum import UserRole, UserStatus
from app.repositories.user_repository import UserRepository
from app.schemas.pydantic.user import UserAuth, UserCreate, UserFilter, UserUpdate
from tests.integration.helpers.names import (
    ADMIN_USER_PASSWORD,
    REGULAR_USER_PASSWORD,
    test_password as password_for,
    unique_name,
)
from tests.integration.fixtures.users import telegram_chat_id
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
            UserAuth(
                credentials=admin_user.login + "invalid",
                password=ADMIN_USER_PASSWORD,
            )
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
    org_name = service.get(regular_user.uuid).grafana_org_name

    link = await service.generate_verification_link()
    code = link.replace(f"{settings.pu_telegram_bot_link}?start=", "")
    logging.info(code)

    await service.verification(telegram_chat_id(configured=True), code)

    redis = await anext(get_redis_session())
    linked = service.get(regular_user.uuid)
    assert await redis.get(code) is None
    assert linked.grafana_org_name == org_name
    assert linked.status == UserStatus.ACTIVE
    assert linked.telegram_chat_id


def test_block_unblock_user(
    database, cc, admin_user, admin_user_token, regular_user
) -> None:
    service = user_service(database, cc, admin_user_token)
    repository = UserRepository(db=database)

    for user in (regular_user, admin_user):
        logging.info(user.uuid)
        org_name = repository.get(User(uuid=user.uuid)).grafana_org_name
        service.block(user.uuid)
        blocked = repository.get(User(uuid=user.uuid))
        assert blocked.status == UserStatus.BLOCKED
        assert blocked.grafana_org_name == org_name

        service.unblock(user.uuid)
        refreshed = repository.get(User(uuid=user.uuid))
        assert refreshed.status == UserStatus.ACTIVE
        assert refreshed.grafana_org_name == org_name


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
    old_password = extra_user._test_password
    token = user_service(database, cc, None).get_token(
        UserAuth(credentials=extra_user.login, password=old_password)
    )
    service = user_service(database, cc, token)
    service.update(UserUpdate(password="password1"))

    new_token = user_service(database, cc, None).get_token(
        UserAuth(credentials=extra_user.login, password="password1")
    )
    assert new_token
    with pytest.raises(NoAccessError):
        user_service(database, cc, None).get_token(
            UserAuth(credentials=extra_user.login, password=old_password)
        )


def test_get_user(database, cc, regular_user, regular_user_token) -> None:
    service = user_service(database, cc, regular_user_token)
    fetched = service.get(regular_user.uuid)
    assert fetched.uuid == regular_user.uuid
    assert fetched.login == regular_user.login


def test_create_user_invalid_password(database, cc) -> None:
    service = user_service(database, cc, None)
    with pytest.raises(UserError):
        service.create(UserCreate(login=unique_name("badpw"), password="short"))


def test_created_user_is_regular_user(extra_user) -> None:
    assert extra_user.role == UserRole.USER


def test_blocked_user_token(
    database, cc, extra_user, extra_user_token, admin_user_token
) -> None:
    fetched = user_service(database, cc, extra_user_token).get(extra_user.uuid)
    assert fetched.uuid == extra_user.uuid

    user_service(database, cc, admin_user_token).block(extra_user.uuid)
    with pytest.raises(NoAccessError):
        user_service(database, cc, extra_user_token).get(extra_user.uuid)


def test_get_grafana_token(
    database, cc, regular_user, regular_user_token
) -> None:
    grafana_token = user_service(
        database, cc, regular_user_token
    ).get_grafana_token()
    assert grafana_token
    fetched = user_service(database, cc, grafana_token).get(regular_user.uuid)
    assert fetched.uuid == regular_user.uuid


def test_set_owner_cli_rejects_bad_args() -> None:
    from scripts.set_owner import main

    assert main([]) == 2
    assert main(["not-a-uuid"]) == 2
    assert main([str(uuid.uuid4()), str(uuid.uuid4())]) == 2


def test_set_owner_cli_missing_user() -> None:
    from scripts.set_owner import main

    assert main([str(uuid.uuid4())]) == 1


def test_assign_owner_replaces_previous(database, cc, extra_user) -> None:
    from scripts.set_owner import assign_owner

    repository = UserRepository(db=database)
    previous = user_service(database, cc, None).create(
        UserCreate(login=unique_name("prev"), password=password_for("testtest2"))
    )
    try:
        repository.set_single_owner(previous.uuid)
        assign_owner(extra_user.uuid)
        database.expire_all()

        assert repository.get(User(uuid=previous.uuid)).role == UserRole.USER
        assert repository.get(User(uuid=extra_user.uuid)).role == UserRole.OWNER
        with pytest.raises(UserError):
            repository.set_single_owner(uuid.uuid4())
    finally:
        repository.delete(User(uuid=previous.uuid))
        extra_user.role = UserRole.USER
        repository.update(extra_user.uuid, extra_user)


def test_owner_grants_and_revokes_admin(database, cc, extra_user) -> None:
    repository = UserRepository(db=database)
    repository.set_single_owner(extra_user.uuid)
    target = None
    try:
        token = user_service(database, cc, None).get_token(
            UserAuth(
                credentials=extra_user.login,
                password=extra_user._test_password,
            )
        )
        service = user_service(database, cc, token)
        target = user_service(database, cc, None).create(
            UserCreate(
                login=unique_name("adm"),
                password=password_for("testtest3"),
            )
        )

        granted = service.grant_admin(target.uuid)
        assert granted.role == UserRole.ADMIN
        revoked = service.revoke_admin(target.uuid)
        assert revoked.role == UserRole.USER
        assert repository.get(User(uuid=extra_user.uuid)).role == UserRole.OWNER
    finally:
        if target is not None:
            repository.delete(User(uuid=target.uuid))
        extra_user.role = UserRole.USER
        repository.update(extra_user.uuid, extra_user)


def test_grant_admin_without_owner(
    database, cc, regular_user, regular_user_token, admin_user_token
) -> None:
    with pytest.raises(NoAccessError):
        user_service(database, cc, regular_user_token).grant_admin(
            regular_user.uuid
        )
    with pytest.raises(NoAccessError):
        user_service(database, cc, admin_user_token).grant_admin(
            regular_user.uuid
        )
    with pytest.raises(NoAccessError):
        user_service(database, cc, admin_user_token).revoke_admin(
            regular_user.uuid
        )


def test_get_many_user(database, cc, admin_user_token, test_hash, regular_user) -> None:
    service = user_service(database, cc, admin_user_token)
    count, users = service.list(
        UserFilter.unlimited(
            search_string=test_hash,
            role=[UserRole.USER],
        )
    )
    assert any(user.uuid == regular_user.uuid for user in users)
    assert count >= 1
