from http.client import HTTPException
from typing import Annotated, Optional

import jwt
from fastapi import Depends, Header
from fastapi import status as http_status

from app import settings
from app.domain.user_model import User
from app.repositories.user_repository import UserRepository


def get_jwt_token(token: Annotated[str | None, Header()]):
    return token


class UserAuthService:

    user_repository = UserRepository()
    jwt_token: Optional[str] = None

    def __init__(
        self,
        user_repository: UserRepository = Depends(),
        jwt_token: str = Depends(get_jwt_token)
    ) -> None:
        self.user_repository = user_repository
        self.jwt_token = jwt_token

    def token_required(self):
        try:
            data = jwt.decode(self.jwt_token, settings.secret_key, algorithms=['HS256'])
        except jwt.exceptions.ExpiredSignatureError:
            raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail=f"No Access")
        except jwt.exceptions.InvalidTokenError:
            raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail=f"No Access")

        user = self.user_repository.get(User(uuid=data['uuid']))

        # проверяет существование пользователя
        if not user:
            raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail=f"No Access")
