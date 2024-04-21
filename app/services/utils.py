from typing import Annotated

from fastapi import HTTPException
from fastapi import status as http_status
from fastapi import Header

from app.domain.user_model import User


def get_jwt_token(token: Annotated[str | None, Header()] = None):
    return token


def creator_check(user: User, obj: any):
    if not user.uuid == obj.creator_uuid:
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail=f"No access")


def merge_two_dict_first_priority(first: dict, two: dict) -> dict:
    return {**two, **first}
