from datetime import timedelta, datetime
from http.client import HTTPException
from typing import Optional

import jwt
from fastapi import Depends, params
from fastapi import HTTPException
from fastapi import status as http_status

from app import settings
from app.domain.unit_model import Unit
from app.domain.user_model import User
from app.repositories.enum import UserRole, AgentType
from app.repositories.unit_repository import UnitRepository
from app.repositories.user_repository import UserRepository
from app.services.utils import get_jwt_token


class AccessService:
    user_repository = UserRepository()
    unit_repository = UnitRepository()
    jwt_token: Optional[str] = None
    current_agent: Optional[User] = None

    def __init__(
        self,
        user_repository: UserRepository = Depends(),
        unit_repository: UnitRepository = Depends(),
        jwt_token: str = Depends(get_jwt_token),
    ) -> None:
        self.user_repository = user_repository
        self.unit_repository = unit_repository
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

            if data['type'] == AgentType.USER.value:
                agent = self.user_repository.get(User(uuid=data['uuid']))
            else:
                agent = self.unit_repository.get(Unit(uuid=data['uuid']))

            if not agent:
                raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail=f"No Access")

            self.current_agent = agent
        else:
            self.current_agent = User(role=UserRole.BOT.value)

    def access_check(self, available_user_role: list[UserRole], is_unit_available: bool = False):
        if isinstance(self.current_agent, User):
            if self.current_agent.role not in [role.value for role in available_user_role]:
                raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail=f"No access")
        elif isinstance(self.current_agent, Unit):
            if not is_unit_available:
                raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail=f"No access")

    @staticmethod
    def generate_user_token(user: User) -> str:
        access_token_exp = datetime.utcnow() + timedelta(seconds=int(settings.auth_token_expiration))

        token = jwt.encode(
            {'uuid': str(user.uuid), 'type': AgentType.USER.value, 'exp': access_token_exp},
            settings.secret_key,
            'HS256',
        )

        return token

    @staticmethod
    def generate_unit_token(unit: Unit) -> str:
        token = jwt.encode(
            {'uuid': str(unit.uuid), 'type': AgentType.UNIT.value},
            settings.secret_key,
            'HS256',
        )

        return token
