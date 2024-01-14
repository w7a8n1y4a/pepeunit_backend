from datetime import datetime, timedelta

import jwt

from typing import Annotated

from fastapi import Depends, Header, HTTPException
from fastapi import status as http_status
from sqlmodel import Session, select

from app import settings
from app.core.db import get_session
from app.modules.unit.sql_models import Unit

from pydantic import BaseModel


class Context:
    """Бизнес контекст приложения"""

    def __init__(self, db: Session, unit: Unit):
        self.db: Session = db
        self.unit: Unit = unit


class Item(BaseModel):
    username: str


def generate_unit_access_token(unit: Unit) -> str:
    """Генерирует вечный авторизационный токен для Unit"""

    # todo отзыв авторизации

    access_token = jwt.encode(
        {'uuid': str(unit.uuid)},
        settings.secret_key,
        'HS256',
    )

    return access_token


def unit_token_required(item: Item, db: Session = Depends(get_session)):
    """Создание бизнес контекста резольверов"""

    print(item.username)

    # проверяет что токен отправлен
    if not item.username:
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail=f"No Access")

    # декодирует токен на составляющие
    try:
        data = jwt.decode(item.username[5:], settings.secret_key, algorithms=['HS256'])
    except jwt.exceptions.ExpiredSignatureError:
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail=f"No Access")
    except jwt.exceptions.InvalidTokenError:
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail=f"No Access")

    unit = db.get(Unit, data['uuid'])

    # проверяет существование пользователя
    if not unit:
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail=f"No Access")

    return Context(db, unit)
