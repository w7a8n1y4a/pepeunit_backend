import asyncio
import json
import logging
import uuid as uuid_pkg
from dataclasses import dataclass
from datetime import datetime

from aiogram import Bot

from app import settings
from app.configs.redis import get_redis_session
from app.domain.notification_model import Notification
from app.dto.enum import (
    FilterTypeValueFiltering,
    FilterTypeValueThreshold,
    NotificationType,
)

TELEGRAM_ALERT_INTERVAL_SECONDS = 10
TELEGRAM_ALERT_TEXT_LIMIT = 4000
DATA_PIPE_ALERT_STREAM = "data_pipe_alerts"
DATA_PIPE_ALERT_GROUP = "backend"
# Stream messages handled with one database session and one delivery batch
DATA_PIPE_ALERT_BATCH = 100
NOTIFICATION_CHANNEL_PREFIX = "notification_user:"


@dataclass(frozen=True)
class Delivery:
    """A stored notification waiting for the socket and telegram push"""

    user_uuid: uuid_pkg.UUID
    telegram_chat_id: str | None
    is_telegram_alert_enable: bool
    notification: Notification


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


class NotificationSocketHub:
    """Pushes a notification only into sockets that are open now"""

    def __init__(self) -> None:
        self._sockets: dict[str, set] = {}

    async def connect(self, user_uuid: str, websocket) -> None:
        self._sockets.setdefault(user_uuid, set()).add(websocket)

    async def disconnect(self, user_uuid: str, websocket) -> None:
        sockets = self._sockets.get(user_uuid)
        if not sockets:
            return
        sockets.discard(websocket)
        if not sockets:
            self._sockets.pop(user_uuid, None)

    async def send(self, user_uuid: str, payload: dict) -> None:
        sockets = list(self._sockets.get(user_uuid, ()))
        for websocket in sockets:
            try:
                await websocket.send_json(payload)
            except Exception:
                await self.disconnect(user_uuid, websocket)


notification_socket_hub = NotificationSocketHub()


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
        entities = data.get("entities") or {}
        lines = ["Instance daily state"]
        lines.extend(f"{key}: {value}" for key, value in entities.items())
        error_count = len(data.get("errors") or [])
        lines.append(f"error and critical groups: {error_count}")
        return "\n".join(lines)

    if notification.type == NotificationType.UNIT_DAILY_SUMMARY.value:
        name = data.get("unit_name") or data.get("unit_uuid")
        return (
            f"Unit daily summary: {name}\n"
            "Open the notification to load error and critical logs"
        )

    return data_pipe_alert_text(data)


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
    """Pushes stored notifications to the user sockets and the telegram queue.

    One Redis connection serves the whole batch, a failed push is logged and
    never undoes the stored notification.
    """
    if not deliveries:
        return

    session = get_redis_session()
    redis = await anext(session)
    try:
        for delivery in deliveries:
            payload = notification_payload(delivery.notification)
            try:
                await redis.publish(
                    f"{NOTIFICATION_CHANNEL_PREFIX}{delivery.user_uuid}",
                    json.dumps(payload),
                )
            except Exception:
                logging.exception(
                    "Failed to push notification %s to sockets",
                    payload["uuid"],
                )
            if delivery.is_telegram_alert_enable:
                telegram_alert_queue.enqueue(
                    delivery.telegram_chat_id or "",
                    telegram_text(delivery.notification),
                )
    finally:
        await session.aclose()


async def listen_notification_sockets() -> None:
    session = get_redis_session()
    redis = await anext(session)
    pubsub = redis.pubsub()
    await pubsub.psubscribe(f"{NOTIFICATION_CHANNEL_PREFIX}*")
    try:
        async for message in pubsub.listen():
            if message.get("type") != "pmessage":
                continue
            channel = message.get("channel") or ""
            if not channel.startswith(NOTIFICATION_CHANNEL_PREFIX):
                continue
            user_uuid = channel[len(NOTIFICATION_CHANNEL_PREFIX) :]
            data = message.get("data")
            if not isinstance(data, str):
                continue
            await notification_socket_hub.send(user_uuid, json.loads(data))
    finally:
        await pubsub.close()
        await session.aclose()


def _iso(value: datetime) -> str:
    return value.isoformat()
