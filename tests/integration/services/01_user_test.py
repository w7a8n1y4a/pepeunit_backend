import logging
import uuid

import pytest

from app import runtime
from app.configs.errors import NoAccessError, UserError, ValidationError
from app.configs.redis import get_redis_session
from app.domain.user_model import User
from app.dto.enum import UserRole, UserStatus
from app.repositories.user_repository import UserRepository
from app.schemas.pydantic.user import (
    AuthChallengeCreate,
    AuthTokenCreate,
    UserCreate,
    UserFilter,
    UserUpdate,
)
from tests.integration.fixtures.users import telegram_chat_id
from tests.integration.helpers.keys import REGULAR_USER_KEY, fresh_key
from tests.integration.helpers.owner import as_owner, preserve_instance_owner
from tests.integration.helpers.services import token_for, user_service


def test_create_user(regular_user, admin_user) -> None:
    logging.info(regular_user.login)
    logging.info(admin_user.login)
    assert regular_user.login
    assert admin_user.role == UserRole.ADMIN


def test_create_user_without_login(database, cc) -> None:
    service = user_service(database, cc, None)
    created = service.create(UserCreate(public_key=fresh_key().public_key))
    try:
        assert created.login is None
    finally:
        UserRepository(db=database).delete(User(uuid=created.uuid))


def test_create_user_duplicate_public_key(database, cc, regular_user) -> None:
    assert regular_user.public_key == REGULAR_USER_KEY.public_key
    service = user_service(database, cc, None)
    with pytest.raises(UserError):
        service.create(
            UserCreate(public_key=REGULAR_USER_KEY.public_key)
        )


def test_get_auth_token_user(regular_user_token, admin_user_token) -> None:
    assert regular_user_token
    assert admin_user_token


async def test_get_auth_token_invalid_signature(
    database, cc, regular_user
) -> None:
    service = user_service(database, cc, None)
    challenge = await service.create_challenge(
        AuthChallengeCreate(
            hash_public_key=regular_user._test_key.hash_public_key
        )
    )
    with pytest.raises(NoAccessError):
        await service.get_token(
            AuthTokenCreate(
                challenge=challenge,
                signature=fresh_key().sign(challenge),
            )
        )


async def test_get_auth_token_reuses_challenge(
    database, cc, regular_user
) -> None:
    service = user_service(database, cc, None)
    challenge = await service.create_challenge(
        AuthChallengeCreate(
            hash_public_key=regular_user._test_key.hash_public_key
        )
    )
    signature = regular_user._test_key.sign(challenge)
    assert await service.get_token(
        AuthTokenCreate(challenge=challenge, signature=signature)
    )
    with pytest.raises(NoAccessError):
        await service.get_token(
            AuthTokenCreate(challenge=challenge, signature=signature)
        )


async def test_get_auth_challenge_unknown_key(database, cc) -> None:
    service = user_service(database, cc, None)
    with pytest.raises(ValidationError):
        await service.create_challenge(
            AuthChallengeCreate(hash_public_key="a" * 64)
        )


@pytest.mark.telegram
async def test_verification_invalid_code(
    database, cc, regular_user, regular_user_token
) -> None:
    service = user_service(database, cc, regular_user_token)
    with pytest.raises(ValidationError):
        link = await service.generate_verification_link()
        code = link.replace(f"{runtime.get().pu_telegram_bot_link}?start=", "")
        await service.verification(str(1_000_000), code[:-2])


@pytest.mark.telegram
async def test_verification_user(
    database, cc, regular_user, regular_user_token
) -> None:
    service = user_service(database, cc, regular_user_token)
    logging.info(regular_user.uuid)
    org_name = service.get(regular_user.uuid).grafana_org_name

    link = await service.generate_verification_link()
    code = link.replace(f"{runtime.get().pu_telegram_bot_link}?start=", "")
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
    token = token_for(database, cc, extra_user._test_key)
    service = user_service(database, cc, token)
    new_login = extra_user.login[:-1] + "x"
    service.update(UserUpdate(login=new_login))
    renamed = extra_user.login[:-1] + "y"
    service.update(UserUpdate(login=renamed))
    extra_user.login = renamed
    logging.info(renamed)


def test_update_user_login_can_match_another(
    database, cc, extra_user, regular_user
) -> None:
    token = token_for(database, cc, extra_user._test_key)
    service = user_service(database, cc, token)
    updated = service.update(UserUpdate(login=regular_user.login))
    assert updated.login == regular_user.login
    assert updated.uuid != regular_user.uuid


def test_get_user(database, cc, regular_user, regular_user_token) -> None:
    service = user_service(database, cc, regular_user_token)
    fetched = service.get(regular_user.uuid)
    assert fetched.uuid == regular_user.uuid
    assert fetched.login == regular_user.login


def test_create_user_invalid_public_key(database, cc) -> None:
    service = user_service(database, cc, None)
    with pytest.raises(UserError):
        service.create(
            UserCreate(public_key="not-a-key")
        )


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
    database.expire_all()
    instance_owner = repository.get_owner()
    instance_owner_uuid = (
        instance_owner.uuid if instance_owner is not None else None
    )
    previous = user_service(database, cc, None).create(
        UserCreate(public_key=fresh_key().public_key)
    )
    with preserve_instance_owner(database):
        try:
            repository.set_single_owner(previous.uuid)
            assign_owner(extra_user.uuid)
            database.expire_all()

            previous_user = repository.get(User(uuid=previous.uuid))
            assert previous_user.role == UserRole.USER
            promoted = repository.get(User(uuid=extra_user.uuid))
            assert promoted.role == UserRole.OWNER
            with pytest.raises(UserError):
                repository.set_single_owner(uuid.uuid4())
        finally:
            repository.delete(User(uuid=previous.uuid))
            extra_user.role = UserRole.USER
            repository.update(extra_user.uuid, extra_user)

    database.expire_all()
    if instance_owner_uuid is None:
        assert repository.get_owner() is None
    else:
        restored = repository.get(User(uuid=instance_owner_uuid))
        assert restored.role == UserRole.OWNER


def test_owner_grants_and_revokes_admin(database, cc, extra_user) -> None:
    repository = UserRepository(db=database)
    target = None
    with as_owner(database, extra_user):
        try:
            token = token_for(database, cc, extra_user._test_key)
            service = user_service(database, cc, token)
            target = user_service(database, cc, None).create(
                UserCreate(public_key=fresh_key().public_key)
            )

            granted = service.grant_admin(target.uuid)
            assert granted.role == UserRole.ADMIN
            revoked = service.revoke_admin(target.uuid)
            assert revoked.role == UserRole.USER
            owner = repository.get(User(uuid=extra_user.uuid))
            assert owner.role == UserRole.OWNER
        finally:
            if target is not None:
                repository.delete(User(uuid=target.uuid))


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
