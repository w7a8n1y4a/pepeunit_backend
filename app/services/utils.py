import uuid as uuid_pkg
from typing import Annotated

from fastapi import Depends
from fastapi.security import APIKeyHeader

from app import settings
from app.repositories.enum import GlobalPrefixTopic


def token_depends(
    jwt_token: Annotated[str | None, Depends(APIKeyHeader(name="x-auth-token", auto_error=False))] = None
):
    return jwt_token


def merge_two_dict_first_priority(first: dict, two: dict) -> dict:
    return {**two, **first}


def remove_none_value_dict(data: dict) -> dict:
    return {k: v for k, v in data.items() if v is not None}


def get_topic_name(node_uuid: uuid_pkg.UUID, topic_name: str):
    main_topic = f'{settings.backend_domain}/{node_uuid}'
    main_topic += (
        GlobalPrefixTopic.BACKEND_SUB_PREFIX
        if topic_name[-len(GlobalPrefixTopic.BACKEND_SUB_PREFIX) :] == GlobalPrefixTopic.BACKEND_SUB_PREFIX
        else ''
    )

    return main_topic
