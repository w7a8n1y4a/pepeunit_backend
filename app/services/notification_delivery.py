import asyncio
import logging
import uuid as uuid_pkg
from collections.abc import AsyncIterator

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
from app.schemas.pydantic.notification import (
    DataPipeAlertData,
    InstanceDailyStateData,
    UnitDailySummaryData,
)


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


class NotificationMessage:
    """Telegram text of one stored notification"""

    @classmethod
    def text(cls, notification: Notification) -> str:
        match NotificationType(notification.type):
            case NotificationType.INSTANCE_DAILY_STATE:
                rendered = cls._instance_daily_state(
                    InstanceDailyStateData.model_validate(notification.data)
                )
            case NotificationType.UNIT_DAILY_SUMMARY:
                rendered = cls._unit_daily_summary(
                    UnitDailySummaryData.model_validate(notification.data)
                )
            case NotificationType.DATA_PIPE_ALERT:
                rendered = cls._data_pipe_alert(
                    DataPipeAlertData.model_validate(notification.data)
                )
            case _:
                msg = f"Unknown notification type: {notification.type}"
                raise ValueError(msg)
        return rendered

    @classmethod
    def _instance_daily_state(cls, data: InstanceDailyStateData) -> str:
        lengths = None
        if data.errors is None:
            table = [["Loki did not return data"]]
        else:
            table = [
                ["Count", "Message"],
                *[
                    [error.count, error.message or "-"]
                    for error in data.errors
                ],
            ]
            lengths = [8, 40]
        return cls._fenced(
            make_monospace_table_with_title(
                table, "Instance daily summary", lengths=lengths
            )
        )

    @classmethod
    def _unit_daily_summary(cls, data: UnitDailySummaryData) -> str:
        if data.units:
            rows = [
                [unit.unit_name or "-", unit.error_count]
                for unit in data.units
            ]
        else:
            rows = [["-", "0"]]
        return cls._fenced(
            make_monospace_table_with_title(
                [["Unit name", "Errors"], *rows], "Unit daily summary"
            )
        )

    @classmethod
    def _data_pipe_alert(cls, data: DataPipeAlertData) -> str:
        lines = [
            "Data pipe alert",
            f"Topic: {data.topic}",
            *[
                f"Value {data.value} {phrase}"
                for phrase in cls._rule_phrases(data)
            ],
        ]
        return "\n".join(lines)

    @classmethod
    def _rule_phrases(cls, data: DataPipeAlertData) -> list[str]:
        """One phrase per violated rule, rules mirror the filters stage"""
        phrases = []
        if data.type_value_threshold is not None:
            phrases.append(cls._threshold_phrase(data))
        if data.type_value_filtering is not None:
            phrases.append(cls._filtering_phrase(data))
        return phrases

    @classmethod
    def _threshold_phrase(cls, data: DataPipeAlertData) -> str:
        low = data.threshold_min
        high = data.threshold_max
        match data.type_value_threshold:
            case FilterTypeValueThreshold.MIN:
                phrase = f"is below {low:g}"
            case FilterTypeValueThreshold.MAX:
                phrase = f"is above {high:g}"
            case FilterTypeValueThreshold.RANGE:
                phrase = f"is outside [{low:g}, {high:g}]"
            case _:
                msg = f"Unknown threshold type: {data.type_value_threshold}"
                raise ValueError(msg)
        return phrase

    @classmethod
    def _filtering_phrase(cls, data: DataPipeAlertData) -> str:
        values = ", ".join(
            cls._text_value(item) for item in data.filtering_values
        )
        match data.type_value_filtering:
            case FilterTypeValueFiltering.WHITELIST:
                phrase = f"is not one of: {values}"
            case FilterTypeValueFiltering.BLACKLIST:
                phrase = f"is one of: {values}"
            case _:
                msg = f"Unknown filtering type: {data.type_value_filtering}"
                raise ValueError(msg)
        return phrase

    @staticmethod
    def _text_value(value: str | float) -> str:
        match value:
            case float():
                rendered = f"{value:g}"
            case str():
                rendered = value
            case _:
                msg = f"Unexpected filtering value: {value!r}"
                raise TypeError(msg)
        return rendered

    @staticmethod
    def _fenced(body: str) -> str:
        # A log line can contain the fence and break Telegram Markdown
        safe = body.replace("```", "'''")
        return f"\n```text\n{safe}```"


class NotificationDelivery:
    """User Redis stream and the telegram queue for stored notifications"""

    # Producers append here, one consumer runs notification_pipe
    INCOMING_STREAM = "notifications"
    STREAM_PREFIX = "notification_user:"
    READ_COUNT = 20
    READ_BLOCK_MS = 5_000
    # Redis must outlive the blocking read, otherwise xread returns empty
    SOCKET_TIMEOUT_FLOOR = 20

    def __init__(self) -> None:
        self.telegram = TelegramAlertQueue()

    def stream_name(self, user_uuid: uuid_pkg.UUID | str) -> str:
        return f"{self.STREAM_PREFIX}{user_uuid}"

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
                        yield f"data: {fields['data']}\n\n"
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
