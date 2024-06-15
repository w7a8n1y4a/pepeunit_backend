from typing import Annotated

from fastapi import HTTPException, Depends
from fastapi import status as http_status
from fastapi.security import APIKeyHeader

from app.domain.user_model import User


def token_depends(
    jwt_token: Annotated[str | None, Depends(APIKeyHeader(name="x-auth-token", auto_error=False))] = None
):
    return jwt_token


def creator_check(user: User, obj: any):
    if not user.uuid == obj.creator_uuid:
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail=f"No access")


def merge_two_dict_first_priority(first: dict, two: dict) -> dict:
    return {**two, **first}


def remove_none_value_dict(data: dict) -> dict:
    return {k: v for k, v in data.items() if v is not None}
