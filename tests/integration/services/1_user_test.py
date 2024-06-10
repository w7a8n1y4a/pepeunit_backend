import asyncio

import fastapi
import pytest

from app import settings
from app.configs.gql import get_user_service
from app.configs.redis import get_redis_session
from app.repositories.enum import UserRole, UserStatus
from app.repositories.user_repository import UserRepository
from app.schemas.pydantic.user import UserCreate, UserAuth, UserUpdate, UserFilter
from tests.integration.conftest import Info


@pytest.mark.run(order=0)
def test_create_user(test_users, database, clear_database) -> None:
    user_service = get_user_service(Info({'db': database, 'jwt_token': None}))

    # create test users
    new_users = []
    for test_user in test_users:
        user = user_service.create(UserCreate(**test_user))
        new_users.append(user)

    assert len(new_users) >= len(test_user)

    pytest.users = new_users

    # check create with exist user login
    with pytest.raises(fastapi.HTTPException):
        user_service.create(UserCreate(**test_users[0]))

    # set admin role for last user
    user_repository = UserRepository(db=database)
    new_users[-1].role = UserRole.ADMIN
    user_repository.update(new_users[-1].uuid, new_users[-1])


@pytest.mark.run(order=1)
def test_get_auth_token_user(test_users, database) -> None:
    user_service = get_user_service(Info({'db': database, 'jwt_token': None}))

    # get token for all test users
    for inc, user in enumerate(pytest.users):
        pytest.user_tokens_dict[user.uuid] = user_service.get_token(
            UserAuth(credentials=user.login, password=test_users[inc]['password'])
        )

    # get token with invalid password
    with pytest.raises(fastapi.HTTPException):
        # get token with invalid password
        user_service.get_token(UserAuth(credentials=pytest.users[0].login, password='invalid password'))

    # get token with invalid login
    with pytest.raises(fastapi.HTTPException):
        user_service.get_token(
            UserAuth(credentials=pytest.users[-1].login + 'invalid', password=test_users[-1]['password'])
        )


@pytest.mark.run(order=2)
async def test_verification_user(database) -> None:

    # check invalid code
    with pytest.raises(fastapi.HTTPException):
        user_service = get_user_service(
            Info({'db': database, 'jwt_token': pytest.user_tokens_dict[pytest.users[0].uuid]})
        )

        code = await user_service.generate_verification_code()
        await user_service.verification(str(1_000_000), code[:-2])

    # set verified status all test users
    codes_list = []
    for inc, user in enumerate(pytest.users, start=1):
        user_service = get_user_service(Info({'db': database, 'jwt_token': pytest.user_tokens_dict[user.uuid]}))

        code = await user_service.generate_verification_code()
        codes_list.append(code)

        await user_service.verification(str(inc * 1_000_000), code)
        assert user.status == UserStatus.VERIFIED.value

    # check del all verification codes in redis
    for code in codes_list:
        redis = await anext(get_redis_session())
        state = await redis.get(code)

        assert state == None


@pytest.mark.run(order=3)
def test_block_unblock_user(database) -> None:
    user_service = get_user_service(Info({'db': database, 'jwt_token': pytest.user_tokens_dict[pytest.users[-1].uuid]}))

    # block unblock users
    for user in pytest.users:
        user_service.block(user.uuid)
        assert user.status == UserStatus.BLOCKED
        user_service.unblock(user.uuid)
        assert user.status == UserStatus.VERIFIED

    # block without admin role
    with pytest.raises(fastapi.HTTPException):
        user_service = get_user_service(
            Info({'db': database, 'jwt_token': pytest.user_tokens_dict[pytest.users[0].uuid]})
        )
        user = pytest.users[0]

        user_service.block(user.uuid)
        assert user.status == UserStatus.BLOCKED

    # unblock without admin role
    with pytest.raises(fastapi.HTTPException):
        user_service = get_user_service(
            Info({'db': database, 'jwt_token': pytest.user_tokens_dict[pytest.users[0].uuid]})
        )
        user = pytest.users[0]

        user_service.unblock(user.uuid)
        assert user.status == UserStatus.VERIFIED


@pytest.mark.run(order=4)
def test_update_user(database) -> None:

    # check change login on new
    current_user = pytest.users[-1]
    user_service = get_user_service(Info({'db': database, 'jwt_token': pytest.user_tokens_dict[current_user.uuid]}))

    new_login = current_user.login + 'test'
    user_service.update(str(current_user.uuid), UserUpdate(login=new_login))

    assert new_login == current_user.login

    # check change login on exist
    with pytest.raises(fastapi.HTTPException):
        current_user = pytest.users[-1]
        user_service = get_user_service(Info({'db': database, 'jwt_token': pytest.user_tokens_dict[current_user.uuid]}))

        other_user = pytest.users[0]
        user_service.update(str(current_user.uuid), UserUpdate(login=other_user.login))

    # check change password
    current_user = pytest.users[0]
    user_service = get_user_service(Info({'db': database, 'jwt_token': pytest.user_tokens_dict[current_user.uuid]}))

    user_service.update(str(current_user.uuid), UserUpdate(login=current_user.login, password='best_new_password'))


@pytest.mark.run(order=5)
def test_get_many_user(database) -> None:

    # check get all test User with role user
    current_user = pytest.users[-1]
    user_service = get_user_service(Info({'db': database, 'jwt_token': pytest.user_tokens_dict[current_user.uuid]}))
    users = user_service.list(
        UserFilter(search_string=pytest.test_hash, role=[UserRole.USER], offset=0, limit=1_000_000)
    )
    assert len(users) == len(pytest.users) - 1
