from fastapi import Depends

from app.repositories.user_repository import UserRepository


class UserAuthService:

    user_repository = UserRepository()

    def __init__(
        self, user_repository: UserRepository = Depends()
    ) -> None:
        self.user_repository = user_repository

