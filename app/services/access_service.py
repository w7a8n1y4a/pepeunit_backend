from datetime import timedelta, datetime
from http.client import HTTPException
from typing import Optional

import jwt
from fastapi import Depends, params
from fastapi import HTTPException
from fastapi import status as http_status

from app import settings
from app.domain.user_model import User
from app.repositories.enum import UserRole
from app.repositories.user_repository import UserRepository
from app.services.utils import get_jwt_token


class AccessService:
    user_repository = UserRepository()
    jwt_token: Optional[str] = None
    current_user: Optional[User] = None

    def __init__(self, user_repository: UserRepository = Depends(), jwt_token: str = Depends(get_jwt_token)) -> None:
        self.user_repository = user_repository
        self.jwt_token = jwt_token
        self.token_required()

    def token_required(self):
        if isinstance(self.jwt_token, params.Depends):
            pass
        elif self.jwt_token is not None:
            try:
                data = jwt.decode(self.jwt_token, settings.secret_key, algorithms=['HS256'])
            except jwt.exceptions.ExpiredSignatureError:
                raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail=f"No Access")
            except jwt.exceptions.InvalidTokenError:
                raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail=f"No Access")

            user = self.user_repository.get(User(uuid=data['uuid']))

            if not user:
                raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail=f"No Access")

            self.current_user = user
        else:
            self.current_user = User(role=UserRole.BOT.value)

    def access_check(self, available_user_role: list[UserRole]) -> bool:
        if self.current_user.role not in [role.value for role in available_user_role]:
            raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail=f"No access")

    @staticmethod
    def generate_user_token(user: User) -> str:
        """Генерирует авторизационный токен"""

        # время жизни токена задаётся из окружения
        access_token_exp = datetime.utcnow() + timedelta(seconds=int(settings.auth_token_expiration))

        token = jwt.encode(
            {'uuid': str(user.uuid), 'exp': access_token_exp},
            settings.secret_key,
            'HS256',
        )

        return token
