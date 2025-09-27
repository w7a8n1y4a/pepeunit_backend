import uuid
import uuid as uuid_pkg
from typing import Annotated

import yaml
from fastapi import Depends
from fastapi.security import APIKeyHeader
from starlette.datastructures import UploadFile as StarletteUploadFile

from app import settings
from app.dto.enum import GlobalPrefixTopic, VisibilityLevel


def token_depends(
    jwt_token: Annotated[
        str | None,
        Depends(APIKeyHeader(name="x-auth-token", auto_error=False)),
    ] = None,
):
    return jwt_token


def merge_two_dict_first_priority(first: dict, two: dict) -> dict:
    return {**two, **first}


def remove_none_value_dict(data: dict) -> dict:
    return {k: v for k, v in data.items() if v is not None}


def get_topic_name(node_uuid: uuid_pkg.UUID, topic_name: str):
    main_topic = f"{settings.backend_domain}/{node_uuid}"
    main_topic += (
        GlobalPrefixTopic.BACKEND_SUB_PREFIX
        if topic_name[-len(GlobalPrefixTopic.BACKEND_SUB_PREFIX) :]
        == GlobalPrefixTopic.BACKEND_SUB_PREFIX
        else ""
    )

    return main_topic


def get_visibility_level_priority(visibility_level: VisibilityLevel) -> int:
    priority_dict = {
        VisibilityLevel.PUBLIC: 0,
        VisibilityLevel.INTERNAL: 1,
        VisibilityLevel.PRIVATE: 2,
    }

    return priority_dict[visibility_level]


async def yml_file_to_dict(yml_file) -> dict:
    content = ""
    if isinstance(yml_file, StarletteUploadFile):
        content = await yml_file.read()
    elif hasattr(yml_file, "read"):
        # Handle Upload type from strawberry
        content = await yml_file.read()

    if isinstance(content, bytes):
        content = content.decode("utf-8")

    return yaml.safe_load(content)


def dict_to_yml_file(yml_dict: dict) -> str:
    yaml_content = yaml.safe_dump(
        yml_dict, allow_unicode=True, default_flow_style=False, sort_keys=False
    )

    filename = f"tmp/data_pipe_yml_{uuid.uuid4()}"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(yaml_content)

    return filename
