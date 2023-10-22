import uuid

from fastapi import Depends
from sqlmodel import Session, select, func

from app.core.db import get_session
from app.modules.user.api_models import UserCreate, UserRead
from app.modules.user.sql_models import User
from app.utils.utils import password_to_hash


def create(data: UserCreate, db: Session = Depends(get_session)) -> UserRead:
    user = User(**data.dict())
    user.cipher_dynamic_salt, user.hashed_password = password_to_hash(data.password)

    db.add(user)
    db.commit()
    db.refresh(user)

    return UserRead(**user.dict())
