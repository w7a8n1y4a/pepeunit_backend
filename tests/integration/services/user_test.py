import asyncio

import fastapi
import pytest

from app import settings
from app.configs.gql import get_user_service
from app.configs.redis import get_redis_session
from app.repositories.enum import UserRole, UserStatus
from app.repositories.user_repository import UserRepository
from app.schemas.pydantic.user import UserCreate, UserAuth
from tests.integration.conftest import Info


@pytest.mark.run(order=0)
def test_create_user(test_users, database, clear_database) -> None:
    user_service = get_user_service(Info({'db': database, 'jwt_token': None}))

    # create test users
    new_users = []
    for test_user in test_users:
        test = user_service.create(UserCreate(**test_user))
        new_users.append(test)

    assert len(new_users) == 2

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
        user_service.get_token(
            UserAuth(credentials=pytest.users[0].login, password='invalid password')
        )

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
            Info({
                'db': database,
                'jwt_token': pytest.user_tokens_dict[pytest.users[0].uuid]
            }
            )
        )

        code = await user_service.generate_verification_code()
        await user_service.verification(str(1_000_000), code[:-2])

    # set verified status all test users
    codes_list = []
    for inc, user in enumerate(pytest.users, start=1):
        user_service = get_user_service(
            Info({
                    'db': database,
                    'jwt_token': pytest.user_tokens_dict[user.uuid]
                }
            )
        )

        code = await user_service.generate_verification_code()
        codes_list.append(code)

        await user_service.verification(str(inc*1_000_000), code)
        assert user.status == UserStatus.VERIFIED.value

    # check del all verification codes in redis
    for code in codes_list:
        redis = await anext(get_redis_session())
        state = await redis.get(code)

        assert state == None




if settings.test:
    @pytest.mark.last
    def test_end(clear_database):
        assert True