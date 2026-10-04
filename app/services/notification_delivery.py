import asyncio
import json
import logging
import uuid as uuid_pkg
from dataclasses import dataclass
from datetime import datetime

from aiogram import Bot
from redis.asyncio import from_url
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

TELEGRAM_ALERT_INTERVAL_SECONDS = 10
TELEGRAM_ALERT_TEXT_LIMIT = 4000
DATA_PIPE_ALERT_STREAM = "data_pipe_alerts"
DATA_PIPE_ALERT_GROUP = "backend"
# Stream messages handled with one database session and one delivery batch
DATA_PIPE_ALERT_BATCH = 100
NOTIFICATION_STREAM_PREFIX = "notification_user:"
NOTIFICATION_STREAM_MAXLEN = 100
_INSTANCE_METRICS = (
    ("user_count", "User"),
    ("repository_registry_count", "RepositoryRegistry"),
    ("repo_count", "Repo"),
    ("unit_count", "Unit"),
    ("unit_node_count", "UnitNode"),
    ("unit_node_edge_count", "UnitNodeEdge"),
)


@dataclass(frozen=True)
class Delivery:
    """A stored notification waiting for the live stream and telegram push"""

    user_uuid: uuid_pkg.UUID
    telegram_chat_id: str | None
    is_telegram_alert_enable: bool
    notification: Notification
    # Daily summaries stay in the database and go to telegram only
    push_sse: bool


class TelegramAlertQueue:
    """Sends at most one telegram message every 10 seconds"""

    def __init__(self) -> None:
        self.queue: asyncio.Queue[tuple[str, str]] | None = None
        self.ready = asyncio.Event()

    def enqueue(self, chat_id: str, text: str) -> None:
        if (
            not settings.pu_ff_telegram_bot_enable
            or not chat_id
            or self.queue is None
        ):
            return
        self.queue.put_nowait((chat_id, text[:TELEGRAM_ALERT_TEXT_LIMIT]))

    async def run(self, bot: Bot) -> None:
        self.queue = asyncio.Queue()
        self.ready.set()
        while True:
            chat_id, text = await self.queue.get()
            try:
                await bot.send_message(chat_id=chat_id, text=text)
            except asyncio.CancelledError:
                raise
            except Exception:
                logging.exception("Failed to send telegram alert")
            await asyncio.sleep(TELEGRAM_ALERT_INTERVAL_SECONDS)


telegram_alert_queue = TelegramAlertQueue()


def notification_payload(notification: Notification) -> dict:
    read_datetime = notification.read_datetime
    return {
        "uuid": str(notification.uuid),
        "create_datetime": _iso(notification.create_datetime),
        "type": notification.type,
        "data": dict(notification.data or {}),
        "is_read": notification.is_read,
        "read_datetime": _iso(read_datetime) if read_datetime else None,
        "target_user_uuid": str(notification.target_user_uuid),
    }


def telegram_text(notification: Notification) -> str:
    data = notification.data or {}
    if notification.type == NotificationType.INSTANCE_DAILY_STATE.value:
        return _instance_daily_state_text(data)
    if notification.type == NotificationType.UNIT_DAILY_SUMMARY.value:
        return _unit_daily_summary_text(data)
    return data_pipe_alert_text(data)


def _instance_daily_state_text(data: dict) -> str:
    entities = data.get("entities") or {}
    metrics = [["Type", "Count"]]
    metrics.extend(
        [label, entities.get(key, 0)] for key, label in _INSTANCE_METRICS
    )
    logs = [["Count", "Message"]]
    errors = data.get("errors") or []
    if errors:
        logs.extend(
            [item.get("count", 0), item.get("message") or "-"]
            for item in errors
        )
    else:
        logs.append(["0", "-"])
    return (
        make_monospace_table_with_title(metrics, "Instance metrics")
        + "\n"
        + make_monospace_table_with_title(
            logs, "Backend logs", lengths=[8, 40]
        )
    )


def _unit_daily_summary_text(data: dict) -> str:
    table = [["Unit name", "Errors"]]
    units = data.get("units") or []
    if units:
        table.extend(
            [item.get("unit_name") or "-", item.get("error_count", 0)]
            for item in units
        )
    else:
        table.append(["-", "0"])
    return make_monospace_table_with_title(table, "Unit daily summary")


def _number(value: object) -> str:
    return f"{value:g}" if isinstance(value, int | float) else str(value)


def _rule_phrases(data: dict) -> list[str]:
    """One phrase per violated rule, rules mirror the filters stage"""
    phrases = []

    type_value_threshold = data.get("type_value_threshold")
    if type_value_threshold:
        low = _number(data.get("threshold_min"))
        high = _number(data.get("threshold_max"))
        phrases.append(
            {
                FilterTypeValueThreshold.MIN.value: f"is below {low}",
                FilterTypeValueThreshold.MAX.value: f"is above {high}",
                FilterTypeValueThreshold.RANGE.value: f"is outside [{low}, {high}]",
            }[type_value_threshold]
        )

    type_value_filtering = data.get("type_value_filtering")
    if type_value_filtering:
        values = ", ".join(
            _number(item) for item in data.get("filtering_values") or []
        )
        phrases.append(
            {
                FilterTypeValueFiltering.WHITE_LIST.value: f"is not one of: {values}",
                FilterTypeValueFiltering.BLACK_LIST.value: f"is one of: {values}",
            }[type_value_filtering]
        )

    return phrases


def data_pipe_alert_text(data: dict) -> str:
    value = data.get("value")
    topic = data.get("topic_name") or data.get("unit_node_uuid")

    lines = ["Data pipe alert", f"Topic: {topic}"]
    lines.extend(f"Value {value} {phrase}" for phrase in _rule_phrases(data))
    return "\n".join(lines)


async def deliver(deliveries: list[Delivery]) -> None:
    """Pushes stored notifications to the user stream and the telegram queue.

    The notification row is already committed. One Redis connection serves the
    whole batch, a failed push is logged and never undoes the stored row.
    Daily summaries skip the stream and go to telegram only.
    """
    if not deliveries:
        return

    session = get_redis_session()
    redis = await anext(session)
    try:
        for delivery in deliveries:
            payload = notification_payload(delivery.notification)
            if delivery.push_sse:
                try:
                    await redis.xadd(
                        f"{NOTIFICATION_STREAM_PREFIX}{delivery.user_uuid}",
                        {"data": json.dumps(payload)},
                        maxlen=NOTIFICATION_STREAM_MAXLEN,
                        approximate=True,
                    )
                except Exception:
                    logging.exception(
                        "Failed to push notification %s to the stream",
                        payload["uuid"],
                    )
            if delivery.is_telegram_alert_enable:
                telegram_alert_queue.enqueue(
                    delivery.telegram_chat_id or "",
                    telegram_text(delivery.notification),
                )
    finally:
        await session.aclose()


async def notification_events(request: Request, user_uuid: str):
    """Holds the request open and yields notifications appended after connect.

    Each open request reads its own Redis stream, so any worker can serve it.
    """
    redis = from_url(
        settings.pu_redis_url,
        encoding="utf-8",
        decode_responses=True,
        socket_connect_timeout=settings.pu_http_connect_timeout,
        # Longer than the xread block, otherwise the read times out empty
        socket_timeout=max(settings.pu_http_timeout, 20),
    )
    stream = f"{NOTIFICATION_STREAM_PREFIX}{user_uuid}"
    last_id = "$"
    try:
        yield ": connected\n\n"
        while True:
            if await request.is_disconnected():
                break
            try:
                response = await redis.xread(
                    {stream: last_id}, count=20, block=5_000
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                logging.exception("Notification stream read failed")
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
        await redis.aclose()


def _iso(value: datetime) -> str:
    return value.isoformat()
