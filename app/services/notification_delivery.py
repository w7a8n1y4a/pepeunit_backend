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

    def enqueue(self, chat_id: str | None, text: str) -> None:
        queue = self._queue
        if (
            not settings.pu_ff_telegram_bot_enable
            or not chat_id
            or queue is None
        ):
            return

        limit = settings.pu_notification_telegram_alert_text_limit
        queue.put_nowait((chat_id, text[:limit]))

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


@dataclass(frozen=True)
class Outgoing:
    """One notification that passed the recipient flags and is ready to send."""

    user_uuid: uuid_pkg.UUID
    chat_id: str | None
    telegram: bool
    notification_type: NotificationType
    text: str
    sse_body: str


def telegram_text(notification_type: NotificationType, text: str) -> str:
    """Telegram wrapper. Tables go out as a monospace block."""
    match notification_type:
        case (
            NotificationType.INSTANCE_DAILY_STATE
            | NotificationType.UNIT_DAILY_SUMMARY
        ):
            rendered = _fenced(text)
        case NotificationType.DATA_PIPE_ALERT:
            rendered = text
        case _:
            rendered = text
    return rendered


def _fenced(body: str) -> str:
    # A log line can contain the fence and break Telegram Markdown
    safe = body.replace("```", "'''")
    return f"\n```text\n{safe}```"


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

    def __init__(self) -> None:
        self.telegram = TelegramAlertQueue()

    def stream_name(self, user_uuid: uuid_pkg.UUID | str) -> str:
        return f"{self.STREAM_PREFIX}{user_uuid}"

    async def deliver(self, outgoing: list[Outgoing]) -> None:
        self._enqueue_telegram(outgoing)
        await self._publish(outgoing)

    def _enqueue_telegram(self, outgoing: list[Outgoing]) -> None:
        for item in outgoing:
            if not item.telegram:
                continue
            self.telegram.enqueue(
                item.chat_id,
                telegram_text(item.notification_type, item.text),
            )

    async def _publish(self, outgoing: list[Outgoing]) -> None:
        if not outgoing:
            return
        session = get_redis_session()
        try:
            redis = await anext(session)
        except Exception as err:
            logging.error(f"Notification stream is unavailable: {err}")
            return
        try:
            for item in outgoing:
                await self._append(redis, item)
        finally:
            await session.aclose()

    async def _append(self, redis, item: Outgoing) -> None:
        try:
            await redis.xadd(
                self.stream_name(item.user_uuid),
                {self.EVENT: item.sse_body},
                maxlen=settings.pu_notification_stream_maxlen,
                approximate=True,
            )
        except asyncio.CancelledError:
            raise
        except Exception as err:
            logging.error(
                f"Failed to publish notification {item.user_uuid}: {err}"
            )

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
                response = await self._read(redis, stream, last_id)
                if response is None:
                    break
                if not response:
                    yield ": ping\n\n"
                    continue
                for _stream_name, messages in response:
                    for message_id, fields in messages:
                        last_id = message_id
                        yield f"data: {fields[self.EVENT]}\n\n"
        finally:
            await session.aclose()

    async def _read(self, redis, stream: str, last_id: str) -> list | None:
        try:
            return await redis.xread(
                {stream: last_id},
                count=self.READ_COUNT,
                block=self.READ_BLOCK_MS,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logging.exception("Notification stream read failed")
            return None


notification_delivery = NotificationDelivery()
