import enum
import json
from typing import AsyncIterator

from redis.asyncio import Redis, from_url

from app import settings
from app.utils.utils import obj_serializer


class DataPipeConfigAction(str, enum.Enum):
    UPDATE = "Update"
    DELETE = "Delete"


async def get_redis_session() -> AsyncIterator[Redis]:
    session = from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
    yield session
    session.close()
    await session.wait_closed()


async def send_to_data_pipe_stream(action: DataPipeConfigAction, unit_node: dict) -> None:
    redis = await anext(get_redis_session())
    try:
        await redis.xadd(
            "backend_data_pipe_nodes",
            {'action': action, 'unit_node_data': json.dumps(unit_node, default=obj_serializer)},
        )
    finally:
        await redis.close()
