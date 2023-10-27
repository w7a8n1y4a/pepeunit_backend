from fastapi import HTTPException
from fastapi import status as http_status
from sqlmodel import Session, select, func

from app.modules.user.sql_models import User
from app.utils.utils import check_password


def is_valid_login(login: str, db: Session):
    if db.exec(select(func.count(User.uuid)).where(User.login == login)).first():
        raise HTTPException(status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Login is not unique")


def is_valid_email(email: str, db: Session):
    if db.exec(select(func.count(User.uuid)).where(User.email == email)).first():
        raise HTTPException(status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Email is not unique")


def is_valid_password(password: str, user: User):
    if not check_password(password, user.hashed_password, user.cipher_dynamic_salt):
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail=f"No access")
