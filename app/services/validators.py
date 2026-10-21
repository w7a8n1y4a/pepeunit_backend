import json
import uuid as uuid_pkg
from json import JSONDecodeError
from typing import Any

from app import settings
from app.configs.error_codes import ErrorCode
from app.configs.errors import (
    CustomJSONDecodeError,
    ValidationError,
)
from app.dto.enum import JsonPayload, NotFoundEntity, UuidEntity
from app.services.utils import get_visibility_level_priority


def is_valid_object(obj: Any, entity: NotFoundEntity) -> None:
    if obj:
        return
    msg = f"{entity} does not exist"
    raise ValidationError(msg, code=ErrorCode.not_found[entity])


def is_valid_json(
    json_str: str,
    name: JsonPayload,
    code: ErrorCode | None = None,
) -> dict:
    try:
        return json.loads(json_str)
    except JSONDecodeError as err:
        resolved = code if code is not None else ErrorCode.json_invalid[name]
        msg = f"Data {name} is invalid"
        raise CustomJSONDecodeError(msg, code=resolved) from err


def is_valid_uuid(
    uuid: str | uuid_pkg.UUID,
    entity: UuidEntity,
) -> uuid_pkg.UUID:
    if isinstance(uuid, uuid_pkg.UUID):
        return uuid

    try:
        return uuid_pkg.UUID(uuid)
    except ValueError as err:
        msg = f"{entity} '{uuid}' is not a UUID"
        raise ValidationError(
            msg, code=ErrorCode.uuid_invalid[entity]
        ) from err


def is_valid_string_with_rules(
    value: str | None,
    alphabet: str = settings.pu_available_name_entity_symbols,
    min_length: int = 4,
    max_length: int = 20,
) -> bool:
    if value is None:
        return False

    current_length = len(value)
    if current_length < min_length or current_length > max_length:
        return False

    return all(char in alphabet for char in value)


def is_valid_visibility_level(parent_obj: Any, child_objs: list) -> None:
    for child_obj in child_objs:
        if get_visibility_level_priority(
            parent_obj.visibility_level
        ) > get_visibility_level_priority(child_obj.visibility_level):
            msg = (
                "The visibility level of the parent object "
                f"{parent_obj.__class__.__name__} is lower than that of "
                f"the child object {child_obj.__class__.__name__}"
            )
            raise ValidationError(
                msg,
                code=ErrorCode.UNIT_VISIBILITY_PARENT_BELOW_CHILD,
            )
