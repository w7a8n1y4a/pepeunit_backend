from fastapi import HTTPException
from fastapi import status as http_status

from app.domain.user_model import User
from app.utils.utils import check_password


def is_valid_object(obj: any):
    if not obj:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=f"No valid request")


def is_valid_password(password: str, user: User):
    if not check_password(password, user.hashed_password, user.cipher_dynamic_salt):
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail=f"No access")
