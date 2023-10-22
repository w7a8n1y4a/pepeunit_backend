from fastapi import Depends
from sqlmodel import Session

from app.core.db import get_session
from app.modules.user.api_models import UserCreate, UserRead
from app.modules.user.sql_models import User
from app.modules.user.validators import is_valid_email, is_valid_login
from app.utils.utils import password_to_hash


def create(data: UserCreate, db: Session = Depends(get_session)) -> UserRead:
    """Создание пользователя"""

    is_valid_login(data.login, db)
    is_valid_email(data.email, db)

    user = User(**data.dict())

    # todo refactor 100 мс можно сэкономить для массовых авторизаций
    user.cipher_dynamic_salt, user.hashed_password = password_to_hash(data.password)

    db.add(user)
    db.commit()
    db.refresh(user)

    return UserRead(**user.dict())
