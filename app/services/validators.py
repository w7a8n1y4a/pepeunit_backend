import json
import uuid as uuid_pkg
from json import JSONDecodeError
from typing import Optional, Sequence, Union

from fastapi import HTTPException
from fastapi import status as http_status

from app import settings
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


def is_valid_uuid(uuid: Union[str, uuid_pkg.UUID]) -> uuid_pkg.UUID:

    if isinstance(uuid, uuid_pkg.UUID):
        return uuid

    try:
        return uuid_pkg.UUID(uuid)
    except ValueError:
        raise HTTPException(status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f'This string is not UUID')


def is_valid_string_with_rules(
    value: Optional[str],
    alphabet: str = settings.available_name_entity_symbols,
    min_length: int = 4,
    max_length: int = 20,
) -> bool:

    if value is None:
        return False

    current_length = len(value)
    if current_length < min_length or current_length > max_length:
        return False

    return all(char in alphabet for char in value)
