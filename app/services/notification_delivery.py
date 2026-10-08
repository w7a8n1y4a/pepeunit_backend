import asyncio
import logging
import uuid as uuid_pkg
from collections.abc import AsyncIterator
from dataclasses import dataclass

from aiogram import Bot
from starlette.requests import Request

from app import settings
from app.configs.redis import get_redis_session
from app.dto.enum import NotificationType


class TelegramAlertQueue:
    """Sends telegram alerts one message at a time"""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[tuple[str, str]] | None = None
        self.ready = asyncio.Event()

    @staticmethod
    def text(notification_type: NotificationType, text: str) -> str:
        if notification_type not in (
            NotificationType.INSTANCE_DAILY_STATE,
            NotificationType.UNIT_DAILY_SUMMARY,
        ):
            return text
        # A log line can contain the fence and break Telegram Markdown
        safe = text.replace("```", "'''")
        return f"\n```text\n{safe}```"

    def enqueue(
        self,
        chat_id: str,
        notification_type: NotificationType,
        text: str,
    ) -> None:
        if not settings.pu_ff_telegram_bot_enable or self._queue is None:
            return

        limit = settings.pu_notification_telegram_alert_text_limit
        rendered = self.text(notification_type, text)
        self._queue.put_nowait((chat_id, rendered[:limit]))

    async def run(self, bot: Bot) -> None:
        self._queue = asyncio.Queue()
        self.ready.set()
        while True:
            chat_id, text = await self._queue.get()
            try:
                await bot.send_message(
                    chat_id=chat_id, text=text, parse_mode="Markdown"
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                logging.exception("Failed to send telegram alert")
            await asyncio.sleep(
                settings.pu_notification_telegram_alert_interval_seconds
            )


class NotificationDelivery:
    """Redis stream of one user and the telegram queue.

    Redis is only the live SSE channel. Stored notifications live in Postgres.
    """

    STREAM_PREFIX = "notification_user:"
    # SSE field that carries the public notification JSON
    EVENT = "data"
    READ_COUNT = 20
    READ_BLOCK_MS = 5_000
    # Redis must outlive the blocking read, otherwise xread returns empty
    SOCKET_TIMEOUT_FLOOR = 20

    @dataclass(frozen=True)
    class Outgoing:
        user_uuid: uuid_pkg.UUID
        chat_id: str
        telegram: bool
        notification_type: NotificationType
        text: str
        sse_body: str

    def __init__(self) -> None:
        self.telegram = TelegramAlertQueue()

    def stream_name(self, user_uuid: uuid_pkg.UUID | str) -> str:
        return f"{self.STREAM_PREFIX}{user_uuid}"

    async def deliver(self, outgoing: list[Outgoing]) -> None:
        for item in outgoing:
            if not item.telegram:
                continue
            self.telegram.enqueue(
                item.chat_id,
                item.notification_type,
                item.text,
            )
        if not outgoing:
            return

        session = get_redis_session()
        try:
            redis = await anext(session)
            for item in outgoing:
                await redis.xadd(
                    self.stream_name(item.user_uuid),
                    {self.EVENT: item.sse_body},
                    maxlen=settings.pu_notification_stream_maxlen,
                    approximate=True,
                )
        finally:
            await session.aclose()

    async def events(
        self, request: Request, user_uuid: str
    ) -> AsyncIterator[str]:
        """Yields notifications appended to the user stream after connect.

        Each open request reads its own Redis stream, so any worker can
        serve it.
        """
        session = get_redis_session(
            socket_timeout=max(
                settings.pu_http_timeout, self.SOCKET_TIMEOUT_FLOOR
            )
        )
        try:
            redis = await anext(session)
            last_id = "$"
            stream = self.stream_name(user_uuid)
            yield ": connected\n\n"
            while not await request.is_disconnected():
                response = await redis.xread(
                    {stream: last_id},
                    count=self.READ_COUNT,
                    block=self.READ_BLOCK_MS,
                )
                if not response:
                    yield ": ping\n\n"
                    continue
                for _stream_name, messages in response:
                    for message_id, fields in messages:
                        last_id = message_id
                        yield f"data: {fields[self.EVENT]}\n\n"
        finally:
            await session.aclose()


notification_delivery = NotificationDelivery()
