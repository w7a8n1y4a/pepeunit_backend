from typing import Union

from fastapi import Depends

from app.domain.user_model import User
from app.repositories.user_repository import UserRepository
from app.schemas.graphql.user import UserCreateInput, UserFilterInput, UserUpdateInput
from app.schemas.pydantic.user import UserCreate, UserUpdate, UserFilter
from app.services.validators import is_valid_object
from app.utils.utils import password_to_hash


class UserService:

    user_repository = UserRepository()

    def __init__(
        self,
        user_repository: UserRepository = Depends(),
    ) -> None:
        self.user_repository = user_repository

    def create(self, data: Union[UserCreate, UserCreateInput]) -> User:

        self.user_repository.is_valid_login(data.login)
        self.user_repository.is_valid_email(data.email)

        user = User(**data.dict())

        # todo refactor first async - 100 мс можно сэкономить для массовых авторизаций
        user.cipher_dynamic_salt, user.hashed_password = password_to_hash(data.password)

        return self.user_repository.create(user)

    def get(self, uuid: str) -> User:
        user = self.user_repository.get(User(uuid=uuid))
        is_valid_object(user)
        return user

    def update(self, uuid: str, data: Union[UserUpdate, UserUpdateInput]) -> User:

        self.user_repository.is_valid_login(data.login, uuid)
        self.user_repository.is_valid_email(data.email, uuid)

        update_user = User(**data.dict())

        if data.password:
            # todo refactor first async - 100 мс можно сэкономить для массовых авторизаций
            update_user.cipher_dynamic_salt, update_user.hashed_password = password_to_hash(data.password)

        return self.user_repository.update(uuid, update_user)

    def delete(self, uuid: str) -> None:
        return self.user_repository.delete(User(uuid=uuid))

    def list(self, filters: Union[UserFilter, UserFilterInput]) -> list[User]:
        return self.user_repository.list(filters)

