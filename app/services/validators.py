import json
from json import JSONDecodeError
from typing import Sequence

from fastapi import HTTPException
from fastapi import status as http_status

from app.domain.user_model import User
from app.utils.utils import check_password


def is_valid_object(obj: any) -> None:
    if not obj:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=f"No valid request")


def is_emtpy_sequence(obj: Sequence):
    if len(obj) != 0:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=f"There are related objects")


def is_valid_password(password: str, user: User) -> None:
    if not check_password(password, user.hashed_password, user.cipher_dynamic_salt):
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail=f"No access")


def is_valid_json(json_str: str) -> dict:
    try:
        env_dict = json.loads(json_str)
    except JSONDecodeError:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST, detail=f'This env_example.json file is not a json serialise'
        )

    return env_dict
