from typing import Union

from fastapi import Depends

from app.domain.user_model import User
from app.repositories.enum import UserRole
from app.repositories.user_repository import UserRepository
from app.schemas.gql.inputs.user import UserCreateInput, UserAuthInput, UserUpdateInput, UserFilterInput
from app.schemas.pydantic.user import UserCreate, UserUpdate, UserFilter, UserAuth
from app.services.access_service import AccessService
from app.services.validators import is_valid_object, is_valid_password
from app.utils.utils import password_to_hash


class UserService:
    user_repository = UserRepository()
    access_service = AccessService()

    def __init__(self, user_repository: UserRepository = Depends(), access_service: AccessService = Depends()) -> None:
        self.user_repository = user_repository
        self.access_service = access_service

    def create(self, data: Union[UserCreate, UserCreateInput]) -> User:
        self.access_service.access_check([UserRole.BOT])
        self.user_repository.is_valid_login(data.login)
        self.user_repository.is_valid_email(data.email)

        user = User(**data.dict())

        # todo refactor first async - 100 мс можно сэкономить для массовых авторизаций
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
        self.access_service.access_check([UserRole.USER])

        self.user_repository.is_valid_login(data.login, uuid)
        self.user_repository.is_valid_email(data.email, uuid)

        update_user = User(**data.dict())

        if data.password:
            # todo refactor first async - 100 мс можно сэкономить для массовых авторизаций
            update_user.cipher_dynamic_salt, update_user.hashed_password = password_to_hash(data.password)

        return self.user_repository.update(uuid, update_user)

    # todo система верификации пользователей

    # todo система блокировки пользователей, unit должны заблокироваться, зависимые юниты надо думать

    def delete(self, uuid: str) -> None:
        self.access_service.access_check([UserRole.ADMIN])
        return self.user_repository.delete(User(uuid=uuid))

    def list(self, filters: Union[UserFilter, UserFilterInput]) -> list[User]:
        self.access_service.access_check([UserRole.ADMIN, UserRole.USER])
        return self.user_repository.list(filters)
