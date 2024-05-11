import datetime
from typing import Union

from fastapi import Depends
from sqlmodel import Session

from app.configs.db import get_session
from app.configs.redis import get_redis_session
from app.domain.user_model import User
from app.repositories.enum import UserRole, UserStatus
from app.repositories.user_repository import UserRepository
from app.schemas.gql.inputs.user import UserCreateInput, UserAuthInput, UserUpdateInput, UserFilterInput
from app.schemas.pydantic.user import UserCreate, UserUpdate, UserFilter, UserAuth
from app.services.access_service import AccessService
from app.services.utils import token_depends
from app.services.validators import is_valid_object, is_valid_password
from app.utils.utils import password_to_hash, generate_random_string


class UserService:
    def __init__(self, db: Session = Depends(get_session), jwt_token: str = Depends(token_depends)) -> None:
        self.user_repository = UserRepository(db)
        self.access_service = AccessService(db, jwt_token)

    def create(self, data: Union[UserCreate, UserCreateInput]) -> User:
        self.access_service.access_check([UserRole.BOT])
        self.user_repository.is_valid_login(data.login)

        user = User(**data.dict())

        user.role = UserRole.USER.value
        user.status = UserStatus.UNVERIFIED.value
        user.create_datetime = datetime.datetime.utcnow()

        user.cipher_dynamic_salt, user.hashed_password = password_to_hash(data.password)

        return self.user_repository.create(user)

    def get(self, uuid: str) -> User:
        self.access_service.access_check([UserRole.USER, UserRole.ADMIN])
        user = self.user_repository.get(User(uuid=uuid))
        is_valid_object(user)
        return user

    def get_token(self, data: Union[UserAuth, UserAuthInput]) -> str:
        self.access_service.access_check([UserRole.BOT])

        user = self.user_repository.get_user_by_credentials(data.credentials)

        is_valid_object(user)
        is_valid_password(data.password, user)

        return self.access_service.generate_user_token(user)

    def update(self, uuid: str, data: Union[UserUpdate, UserUpdateInput]) -> User:
        self.access_service.access_check([UserRole.USER, UserRole.ADMIN])

        self.user_repository.is_valid_login(data.login, uuid)

        update_user = User(**data.dict())

        if data.password:
            update_user.cipher_dynamic_salt, update_user.hashed_password = password_to_hash(data.password)

        return self.user_repository.update(uuid, update_user)

    async def generate_verification_code(self) -> str:
        self.access_service.access_check([UserRole.USER, UserRole.ADMIN])
        redis = await anext(get_redis_session())

        code = generate_random_string(6)
        await redis.set(code, str(self.access_service.current_agent.uuid), ex=60)

        return code

    async def verification(self, telegram_chat_id: str, verification_code: str):

        redis = await anext(get_redis_session())
        uuid = await redis.get(verification_code)
        await redis.delete(verification_code)

        print(uuid)

        user = self.user_repository.get(User(uuid=uuid))

        is_valid_object(user)
        self.user_repository.is_valid_telegram_chat_id(telegram_chat_id, user.uuid)

        return self.user_repository.update(user.uuid, User(
            status=UserStatus.VERIFIED.value,
            telegram_chat_id=telegram_chat_id
        ))

    def block(self, uuid: str) -> None:
        self.access_service.access_check([UserRole.ADMIN])
        self.user_repository.update(uuid, User(status=UserStatus.BLOCKED.value))

    def unblock(self, uuid: str) -> None:
        self.access_service.access_check([UserRole.ADMIN])

        user = self.user_repository.get(User(uuid=uuid))

        status = UserStatus.VERIFIED.value if user.telegram_chat_id else UserStatus.UNVERIFIED.value

        self.user_repository.update(uuid, User(status=status))

    def list(self, filters: Union[UserFilter, UserFilterInput]) -> list[User]:
        self.access_service.access_check([UserRole.ADMIN, UserRole.USER])
        return self.user_repository.list(filters)
