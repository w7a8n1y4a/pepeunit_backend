import datetime
import uuid as uuid_pkg
from typing import Optional, Union

from fastapi import Depends
from sqlmodel import Session

from app import settings
from app.configs.db import get_session
from app.configs.redis import get_redis_session
from app.domain.user_model import User
from app.dto.agent.abc import AgentUser
from app.dto.enum import AgentType, UserRole, UserStatus
from app.repositories.user_repository import UserRepository
from app.schemas.gql.inputs.user import UserAuthInput, UserCreateInput, UserFilterInput, UserUpdateInput
from app.schemas.pydantic.user import UserAuth, UserCreate, UserFilter, UserUpdate
from app.services.access_service import AccessService
from app.services.utils import token_depends
from app.services.validators import is_valid_object, is_valid_password
from app.utils.utils import generate_random_string, password_to_hash


class UserService:
    def __init__(
        self,
        db: Session = Depends(get_session),
        jwt_token: Optional[str] = Depends(token_depends),
        is_bot_auth: bool = False,
    ) -> None:
        self.user_repository = UserRepository(db)
        self.access_service = AccessService(db, jwt_token, is_bot_auth)

    def create(self, data: Union[UserCreate, UserCreateInput]) -> User:
        self.access_service.authorization.check_access([AgentType.BOT])
        self.user_repository.is_valid_login(data.login)
        self.user_repository.is_valid_password(data.password)

        user = User(**data.dict())

        # first user is Admin
        user_count = self.user_repository.get_all_count()
        user.role = UserRole.USER if user_count > 0 else UserRole.ADMIN

        user.status = UserStatus.UNVERIFIED
        user.create_datetime = datetime.datetime.utcnow()

        user.cipher_dynamic_salt, user.hashed_password = password_to_hash(data.password)

        return self.user_repository.create(user)

    def get(self, uuid: uuid_pkg.UUID) -> User:
        self.access_service.authorization.check_access([AgentType.USER])
        user = self.user_repository.get(User(uuid=uuid))
        is_valid_object(user)
        return user

    def get_token(self, data: Union[UserAuth, UserAuthInput]) -> str:
        self.access_service.authorization.check_access([AgentType.BOT])

        user = self.user_repository.get_user_by_credentials(data.credentials)
        is_valid_object(user)
        is_valid_password(data.password, user)

        return AgentUser(**user.dict()).generate_agent_token()

    def update(self, data: Union[UserUpdate, UserUpdateInput]) -> User:
        self.access_service.authorization.check_access([AgentType.USER])
        user = self.user_repository.get(User(uuid=self.access_service.current_agent.uuid))
        is_valid_object(user)

        if data.login:
            self.user_repository.is_valid_login(data.login, user.uuid)
            user.login = data.login

        if data.password:
            self.user_repository.is_valid_password(data.password)
            user.cipher_dynamic_salt, user.hashed_password = password_to_hash(data.password)

        return self.user_repository.update(user.uuid, user)

    async def generate_verification_link(self) -> str:
        self.access_service.authorization.check_access([AgentType.USER])
        redis = await anext(get_redis_session())

        code = generate_random_string(8)
        await redis.set(code, str(self.access_service.current_agent.uuid), ex=60)

        return f'{settings.telegram_bot_link}?start={code}'

    async def verification(self, telegram_chat_id: str, verification_code: str):

        redis = await anext(get_redis_session())
        uuid = await redis.get(verification_code)
        is_valid_object(uuid)
        await redis.delete(verification_code)

        user = self.user_repository.get(User(uuid=uuid))
        is_valid_object(user)
        self.user_repository.is_valid_telegram_chat_id(telegram_chat_id, user.uuid)

        return self.user_repository.update(
            user.uuid, User(status=UserStatus.VERIFIED, telegram_chat_id=telegram_chat_id)
        )

    def block(self, uuid: uuid_pkg.UUID) -> None:
        self.access_service.authorization.check_access([AgentType.USER], [UserRole.ADMIN])
        self.user_repository.update(uuid, User(status=UserStatus.BLOCKED))

    def unblock(self, uuid: uuid_pkg.UUID) -> None:
        self.access_service.authorization.check_access([AgentType.USER], [UserRole.ADMIN])

        user = self.user_repository.get(User(uuid=uuid))
        is_valid_object(user)

        status = UserStatus.VERIFIED if user.telegram_chat_id else UserStatus.UNVERIFIED

        self.user_repository.update(uuid, User(status=status))

    def list(self, filters: Union[UserFilter, UserFilterInput]) -> tuple[int, list[User]]:
        self.access_service.authorization.check_access([AgentType.USER])
        return self.user_repository.list(filters)
