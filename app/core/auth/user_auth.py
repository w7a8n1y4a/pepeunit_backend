from datetime import datetime, timedelta
from functools import wraps

import jwt

from typing import Annotated

from fastapi import Depends, Header, HTTPException
from fastapi import status as http_status
from sqlmodel import Session, select

from app import settings
from app.core.db import get_session
from app.modules.user.enum import UserRole
from app.modules.user.sql_models import User


class Context:
    """Бизнес контекст приложения"""

    def __init__(self, db: Session, user: User):
        self.db: Session = db
        self.user: User = user


def generate_user_access_token(user: User) -> str:
    """Генерирует авторизационный токен"""

    # время жизни токена задаётся из окружения
    access_token_exp = datetime.utcnow() + timedelta(seconds=int(settings.auth_token_expiration))

    access_token = jwt.encode(
        {'uuid': str(user.uuid), 'exp': access_token_exp},
        settings.secret_key,
        'HS256',
    )

    return access_token


def user_token_required(auth_token: Annotated[str | None, Header()], db: Session = Depends(get_session)):
    """Создание бизнес контекста резольверов"""

    # проверяет что токен отправлен
    if not auth_token:
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail=f"No Access")

    # декодирует токен на составляющие
    try:
        data = jwt.decode(auth_token, settings.secret_key, algorithms=['HS256'])
    except jwt.exceptions.ExpiredSignatureError:
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail=f"No Access")
    except jwt.exceptions.InvalidTokenError:
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail=f"No Access")

    user = db.exec(select(User).where(User.uuid == data['uuid'])).first()

    # проверяет существование пользователя
    if not user:
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail=f"No Access")

    return Context(db, user)


def check_access(roles: list[UserRole] = None):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):

            # если переданный роли, но роли пользователя нет в списке
            if roles is not None and args[1].role not in roles:
                raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail=f"No Access")

            return fn(*args, **kwargs)


