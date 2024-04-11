from typing import AsyncIterator

from aioredis import from_url, Redis

from app import settings


async def get_redis_session() -> AsyncIterator[Redis]:
    session = from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
    yield session
    session.close()
    await session.wait_closed()
