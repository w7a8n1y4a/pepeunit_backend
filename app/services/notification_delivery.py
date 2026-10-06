import asyncio
import logging
import uuid as uuid_pkg
from dataclasses import dataclass

from aiogram import Bot
from starlette.requests import Request

from app import settings
from app.configs.redis import get_redis_session
from app.domain.notification_model import Notification
from app.dto.enum import (
    FilterTypeValueFiltering,
    FilterTypeValueThreshold,
    NotificationType,
)
from app.schemas.bot.utils import make_monospace_table_with_title
from app.schemas.pydantic.notification import NotificationRead


@dataclass(frozen=True)
class Delivery:
    """A stored notification waiting for the live stream and telegram push"""

    user_uuid: uuid_pkg.UUID
    telegram_chat_id: str | None
    is_telegram_alert_enable: bool
    notification: Notification


class TelegramAlertQueue:
    """Sends telegram alerts one message at a time"""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[tuple[str, str, str | None]] | None = None
        self.ready = asyncio.Event()

    def enqueue(
        self, chat_id: str, text: str, parse_mode: str | None = None
    ) -> None:
        queue = self._queue
        if (
            settings.pu_ff_telegram_bot_enable
            and chat_id
            and queue is not None
        ):
            limit = settings.pu_notification_telegram_alert_text_limit
            queue.put_nowait((chat_id, text[:limit], parse_mode))

    async def run(self, bot: Bot) -> None:
        self._queue = asyncio.Queue()
        self.ready.set()
        while True:
            chat_id, text, parse_mode = await self._queue.get()
            try:
                await bot.send_message(
                    chat_id=chat_id, text=text, parse_mode=parse_mode
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                logging.exception("Failed to send telegram alert")
            await asyncio.sleep(
                settings.pu_notification_telegram_alert_interval_seconds
            )


class NotificationMessage:
    """Telegram text of one stored notification"""

    DAILY_TYPES = frozenset(
        {
            NotificationType.INSTANCE_DAILY_STATE.value,
            NotificationType.UNIT_DAILY_SUMMARY.value,
        }
    )
    INSTANCE_COLUMN_LENGTHS = (8, 40)
    MARKDOWN = "Markdown"

    @classmethod
    def text(cls, notification: Notification) -> str:
        data = notification.data or {}
        if notification.type == NotificationType.INSTANCE_DAILY_STATE.value:
            rendered = cls._instance_daily_state(data)
        elif notification.type == NotificationType.UNIT_DAILY_SUMMARY.value:
            rendered = cls._unit_daily_summary(data)
        else:
            rendered = cls._data_pipe_alert(data)
        return rendered

    @classmethod
    def parse_mode(cls, notification: Notification) -> str | None:
        mode = None
        if notification.type in cls.DAILY_TYPES:
            mode = cls.MARKDOWN
        return mode

    @classmethod
    def _instance_daily_state(cls, data: dict) -> str:
        errors = data.get("errors")
        if isinstance(errors, list):
            table = [["Count", "Message"]]
            table.extend(
                [item.get("count", 0), item.get("message") or "-"]
                for item in errors
            )
            lengths = list(cls.INSTANCE_COLUMN_LENGTHS)
        else:
            table = [["Loki did not return data"]]
            lengths = None
        return cls._fenced(
            make_monospace_table_with_title(
                table, "Instance daily summary", lengths=lengths
            )
        )

    @classmethod
    def _unit_daily_summary(cls, data: dict) -> str:
        table = [["Unit name", "Errors"]]
        units = data.get("units") or []
        if units:
            table.extend(
                [item.get("unit_name") or "-", item.get("error_count", 0)]
                for item in units
            )
        else:
            table.append(["-", "0"])
        return cls._fenced(
            make_monospace_table_with_title(table, "Unit daily summary")
        )

    @classmethod
    def _data_pipe_alert(cls, data: dict) -> str:
        value = data.get("value")
        topic = data.get("topic_name") or data.get("unit_node_uuid")
        lines = ["Data pipe alert", f"Topic: {topic}"]
        lines.extend(
            f"Value {value} {phrase}" for phrase in cls._rule_phrases(data)
        )
        return "\n".join(lines)

    @classmethod
    def _rule_phrases(cls, data: dict) -> list[str]:
        """One phrase per violated rule, rules mirror the filters stage"""
        phrases = []
        threshold = data.get("type_value_threshold")
        if threshold:
            phrases.append(cls._threshold_phrase(data, threshold))
        filtering = data.get("type_value_filtering")
        if filtering:
            phrases.append(cls._filtering_phrase(data, filtering))
        return phrases

    @classmethod
    def _threshold_phrase(cls, data: dict, kind: str) -> str:
        low = cls._number(data.get("threshold_min"))
        high = cls._number(data.get("threshold_max"))
        phrases = {
            FilterTypeValueThreshold.MIN.value: f"is below {low}",
            FilterTypeValueThreshold.MAX.value: f"is above {high}",
            FilterTypeValueThreshold.RANGE.value: (
                f"is outside [{low}, {high}]"
            ),
        }
        return phrases[kind]

    @classmethod
    def _filtering_phrase(cls, data: dict, kind: str) -> str:
        values = ", ".join(
            cls._number(item) for item in data.get("filtering_values") or []
        )
        phrases = {
            FilterTypeValueFiltering.WHITELIST.value: (
                f"is not one of: {values}"
            ),
            FilterTypeValueFiltering.BLACKLIST.value: f"is one of: {values}",
        }
        return phrases[kind]

    @staticmethod
    def _number(value: object) -> str:
        rendered = str(value)
        if isinstance(value, int | float):
            rendered = f"{value:g}"
        return rendered

    @staticmethod
    def _fenced(body: str) -> str:
        # A log line can contain the fence and break Telegram Markdown
        safe = body.replace("```", "'''")
        return f"\n```text\n{safe}```"


class NotificationDelivery:
    """User Redis stream and the telegram queue for stored notifications"""

    STREAM_PREFIX = "notification_user:"
    READ_COUNT = 20
    READ_BLOCK_MS = 5_000
    # Redis must outlive the blocking read, otherwise xread returns empty
    SOCKET_TIMEOUT_FLOOR = 20

    def __init__(self) -> None:
        self.telegram = TelegramAlertQueue()

    def stream_name(self, user_uuid: uuid_pkg.UUID | str) -> str:
        return f"{self.STREAM_PREFIX}{user_uuid}"

    async def push(self, deliveries: list[Delivery]) -> None:
        """Pushes stored notifications to the user stream and telegram.

        The notification row is already committed. One Redis connection
        serves the whole batch. A failed push is logged and never undoes
        the stored row.
        """
        if deliveries:
            session = get_redis_session()
            redis = await anext(session)
            try:
                for delivery in deliveries:
                    await self._push_one(redis, delivery)
            finally:
                await session.aclose()

    async def _push_one(self, redis, delivery: Delivery) -> None:
        notification = delivery.notification
        read = NotificationRead(**notification.dict())
        try:
            await redis.xadd(
                self.stream_name(delivery.user_uuid),
                {"data": read.model_dump_json()},
                maxlen=settings.pu_notification_stream_maxlen,
                approximate=True,
            )
        except Exception:
            logging.exception(
                "Failed to push notification %s to the stream",
                read.uuid,
            )
        if delivery.is_telegram_alert_enable:
            self.telegram.enqueue(
                delivery.telegram_chat_id or "",
                NotificationMessage.text(notification),
                NotificationMessage.parse_mode(notification),
            )

    async def events(self, request: Request, user_uuid: str):
        """Yields notifications appended to the user stream after connect.

        Each open request reads its own Redis stream, so any worker can
        serve it.
        """
        session = get_redis_session(
            socket_timeout=max(
                settings.pu_http_timeout, self.SOCKET_TIMEOUT_FLOOR
            )
        )
        redis = await anext(session)
        stream = self.stream_name(user_uuid)
        last_id = "$"
        try:
            yield ": connected\n\n"
            while True:
                if await request.is_disconnected():
                    break
                response = await self._read(redis, stream, last_id)
                if response is None:
                    break
                if not response:
                    yield ": ping\n\n"
                    continue
                for _stream_name, messages in response:
                    for message_id, fields in messages:
                        last_id = message_id
                        data = fields.get("data")
                        if isinstance(data, str):
                            yield f"data: {data}\n\n"
        finally:
            await session.aclose()

    async def _read(self, redis, stream: str, last_id: str):
        response = None
        try:
            response = await redis.xread(
                {stream: last_id},
                count=self.READ_COUNT,
                block=self.READ_BLOCK_MS,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logging.exception("Notification stream read failed")
        return response


notification_delivery = NotificationDelivery()
