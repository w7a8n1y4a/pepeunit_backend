import json
import uuid as uuid_pkg
from json import JSONDecodeError
from typing import Optional, Sequence, Union

from app import settings
from app.configs.errors import CustomJSONDecodeError, NoAccessError, ValidationError
from app.domain.user_model import User
from app.services.utils import get_visibility_level_priority
from app.utils.utils import check_password


def is_valid_object(obj: any) -> None:
    if not obj:
        raise ValidationError('The object does not exist')


def is_emtpy_sequence(obj: Sequence):
    if len(obj) != 0:
        raise ValidationError('The array was expected to be empty, but it turned out to be full')


def is_valid_password(password: str, user: User) -> None:
    if not check_password(password, user.hashed_password, user.cipher_dynamic_salt):
        raise NoAccessError("Password hash mismatched")


def is_valid_json(json_str: str, name: str) -> dict:
    try:
        return json.loads(json_str)
    except JSONDecodeError:
        raise CustomJSONDecodeError('Data {} is invalid'.format(name))


def is_valid_uuid(uuid: Union[str, uuid_pkg.UUID]) -> uuid_pkg.UUID:

    if isinstance(uuid, uuid_pkg.UUID):
        return uuid

    try:
        return uuid_pkg.UUID(uuid)
    except ValueError:
        raise ValidationError('This {} string is not UUID'.format(uuid))


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


def is_valid_visibility_level(parent_obj: any, child_objs: list) -> None:

    for child_obj in child_objs:
        if get_visibility_level_priority(parent_obj.visibility_level) > get_visibility_level_priority(
            child_obj.visibility_level
        ):
            raise ValidationError(
                'The visibility level of the parent object {} is lower than that of the child object {}'.format(
                    parent_obj.__class__.__name__,
                    child_obj.__class__.__name__,
                )
            )
