from fastapi import Depends, HTTPException
from fastapi import status as http_status
from sqlmodel import Session, select, func, or_

from app.core.auth.user_auth import generate_user_access_token
from app.core.db import get_session
from app.modules.user.api_models import UserCreate, UserRead, UserAuth, AccessToken
from app.modules.user.sql_models import User
from app.modules.user.utils import access_check
from app.modules.user.validators import is_valid_email, is_valid_login, is_valid_password, is_valid_object
from app.utils.utils import password_to_hash


def create(data: UserCreate, db: Session = Depends(get_session)) -> UserRead:
    """Создание пользователя"""

    is_valid_login(data.login, db)
    is_valid_email(data.email, db)

    user = User(**data.dict())

    # todo refactor first async - 100 мс можно сэкономить для массовых авторизаций
    user.cipher_dynamic_salt, user.hashed_password = password_to_hash(data.password)

    db.add(user)
    db.commit()
    db.refresh(user)

    return UserRead(**user.dict())


def create_token(data: UserAuth, db: Session = Depends(get_session)) -> AccessToken:

    user = db.exec(select(User).where(or_(User.login == data.credentials, User.email == data.credentials))).first()

    is_valid_object(user)

    # todo refactor first async - 100 мс можно сэкономить для массовых авторизаций
    is_valid_password(data.password, user)

    return AccessToken(access_token=generate_user_access_token(user))


def get(uuid: str, user: User, db: Session = Depends(get_session)) -> UserRead:

    access_check(user)

    user = db.get(User, uuid)

    is_valid_object(user)

    return UserRead(**user.dict())


def get_current(user: User) -> UserRead:
    return UserRead(**user.dict())
