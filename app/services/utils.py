import uuid as uuid_pkg
from typing import Annotated

import jwt
from fastapi import Depends
from fastapi.security import APIKeyHeader

from app import settings
from app.dto.agent.abc import Agent
from app.repositories.enum import GlobalPrefixTopic, VisibilityLevel


def token_depends(
    jwt_token: Annotated[str | None, Depends(APIKeyHeader(name="x-auth-token", auto_error=False))] = None
):
    return jwt_token


def generate_agent_token(agent: Agent) -> str:
    return jwt.encode({"uuid": str(agent.uuid), "type": agent.type}, settings.backend_secret_key, "HS256")


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


def get_visibility_level_priority(visibility_level: VisibilityLevel) -> int:

    priority_dict = {
        VisibilityLevel.PUBLIC: 0,
        VisibilityLevel.INTERNAL: 1,
        VisibilityLevel.PRIVATE: 2,
    }

    return priority_dict[visibility_level]
