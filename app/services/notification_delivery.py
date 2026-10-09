import asyncio
import logging
import re
import time
import uuid as uuid_pkg
from collections import deque
from collections.abc import AsyncIterator
from contextlib import suppress

from aiogram import Bot
from starlette.requests import Request

from app import settings
from app.configs.redis import get_redis_session
from app.domain.notification_model import Notification
from app.domain.notification_settings_model import NotificationSettings
from app.domain.user_model import User
from app.schemas.pydantic.notification import NotificationRead


class TelegramAlertQueue:
    """Sends telegram alerts at Telegram's own pace.

    A chat receives one message a second. The instance stays under its
    shared rate. Chats take turns, so one chat does not hold the rest.
    """

    _MARKDOWN = re.compile(r"([_*`\[])")

    def __init__(
        self,
        user_interval: float | None = None,
        instance_rate: int | None = None,
    ) -> None:
        self.user_interval = (
            settings.pu_notification_telegram_user_interval_seconds
            if user_interval is None
            else user_interval
        )
        self.instance_rate = (
            settings.pu_notification_telegram_instance_rate
            if instance_rate is None
            else instance_rate
        )
        # Lines still waiting, and the order in which chats take a turn.
        self._lines: dict[str, deque[str]] = {}
        self._turns: deque[str] = deque()
        self._chat_sent_at: dict[str, float] = {}
        self._instance_sent_at: float | None = None
        self._arrived = asyncio.Event()
        self.ready = asyncio.Event()

    @staticmethod
    def text(text: str) -> str:
        """The table or the log, as a monospace block."""
        # A line of the log can contain the fence and break Markdown.
        safe = text.replace("```", "'''")
        return f"\n```text\n{safe}```"

    def plain(self, text: str) -> str:
        """One line. `_` and `*` would otherwise start Markdown."""
        return self._MARKDOWN.sub(r"\\\1", text)

    def enqueue(self, chat_id: str, text: str) -> None:
        if not self.ready.is_set():
            return

        limit = settings.pu_notification_telegram_alert_text_limit
        line = self.plain(text)[:limit]
        waiting = self._lines.get(chat_id)
        if waiting is None:
            waiting = deque()
            self._lines[chat_id] = waiting
            self._turns.append(chat_id)
        waiting.append(line)
        self._arrived.set()

    async def run(self, bot: Bot) -> None:
        self.ready.set()
        while True:
            chat_id, text = await self._wait_for_line()
            await self._send(bot, chat_id, text)
            self._mark_sent(chat_id, time.monotonic())

    async def _send(self, bot: Bot, chat_id: str, text: str) -> None:
        try:
            await bot.send_message(
                chat_id=chat_id, text=text, parse_mode="Markdown"
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logging.exception("Failed to send telegram alert")

    async def _wait_for_line(self) -> tuple[str, str]:
        while True:
            now = time.monotonic()
            ready = self._ready_message(now)
            if ready is not None:
                return ready

            # A line can arrive between the check above and the clear.
            self._arrived.clear()
            now = time.monotonic()
            ready = self._ready_message(now)
            if ready is not None:
                return ready

            delay = self._seconds_until_next(now)
            if delay is None:
                await self._arrived.wait()
            elif delay > 0:
                with suppress(TimeoutError):
                    await asyncio.wait_for(self._arrived.wait(), delay)

    def _ready_message(self, now: float) -> tuple[str, str] | None:
        """One line that both limits allow right now.

        The chat at the front either sends and goes to the back, or
        still has to wait and goes to the back without sending. An
        empty chat leaves the circle.
        """
        if not self._turns or not self._instance_can_send(now):
            return None

        looked_at = 0
        chatting = len(self._turns)
        while looked_at < chatting and self._turns:
            chat_id = self._turns[0]
            waiting = self._lines.get(chat_id)
            if not waiting:
                self._turns.popleft()
                self._lines.pop(chat_id, None)
                chatting -= 1
                continue
            if not self._chat_can_send(chat_id, now):
                self._turns.rotate(-1)
                looked_at += 1
                continue

            text = waiting.popleft()
            self._turns.rotate(-1)
            if not waiting:
                self._turns.pop()
                del self._lines[chat_id]
            return chat_id, text
        return None

    def _seconds_until_next(self, now: float) -> float | None:
        """How long until some waiting chat and the instance may both send."""
        if not self._turns:
            return None
        chat_waits = [
            self._chat_wait(chat_id, now)
            for chat_id in self._turns
            if self._lines.get(chat_id)
        ]
        if not chat_waits:
            return None
        return max(self._instance_wait(now), min(chat_waits))

    def _mark_sent(self, chat_id: str, now: float) -> None:
        self._chat_sent_at[chat_id] = now
        self._instance_sent_at = now

    def _chat_can_send(self, chat_id: str, now: float) -> bool:
        return self._chat_wait(chat_id, now) == 0

    def _instance_can_send(self, now: float) -> bool:
        return self._instance_wait(now) == 0

    def _chat_wait(self, chat_id: str, now: float) -> float:
        sent_at = self._chat_sent_at.get(chat_id)
        if sent_at is None:
            return 0
        return max(0, sent_at + self.user_interval - now)

    def _instance_wait(self, now: float) -> float:
        if self._instance_sent_at is None:
            return 0
        return max(0, self._instance_sent_at + self._instance_gap() - now)

    def _instance_gap(self) -> float:
        return 1 / self.instance_rate


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

    async def deliver(
        self,
        pending: list[tuple[Notification, User, NotificationSettings]],
    ) -> None:
        for notification, user, settings_row in pending:
            if not settings_row.is_telegram_alert_enable:
                continue
            self.telegram.enqueue(
                user.telegram_chat_id,
                notification.small_text,
            )
        if not pending:
            return

        session = get_redis_session()
        try:
            redis = await anext(session)
            for notification, user, _settings_row in pending:
                body = NotificationRead(
                    **notification.dict()
                ).model_dump_json()
                await redis.xadd(
                    self.stream_name(user.uuid),
                    {self.EVENT: body},
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
