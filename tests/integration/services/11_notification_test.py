import asyncio
import json
import logging
import time
import uuid as uuid_pkg
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from pydantic import ValidationError as SchemaValidationError

from app import settings
from app.configs.errors import NoAccessError
from app.configs.redis import get_redis_session
from app.domain.notification_model import Notification
from app.dto.clickhouse.log import UnitLog
from app.dto.enum import (
    AgentType,
    LogLevel,
    NotificationType,
    OperationTaskStatus,
    OperationTaskType,
    UnitNodeTypeEnum,
    UserRole,
)
from app.repositories.notification_settings_repository import (
    NotificationSettingsRepository,
)
from app.repositories.operation_task_repository import (
    OperationTaskRepository,
)
from app.repositories.unit_log_repository import UnitLogRepository
from app.repositories.user_repository import UserRepository
from app.schemas.pydantic.notification import (
    OPERATION_TASK_ALERTS,
    DataPipeAlertData,
    InstanceDailyStateData,
    NotificationFilter,
    NotificationRead,
    NotificationSettingsUpdate,
    UnitDailySummaryData,
)
from app.schemas.pydantic.operation_task import OperationTaskCreate
from app.schemas.pydantic.unit_node import UnitNodeFilter, UnitNodeUpdate
from app.services.notification_delivery import (
    TelegramAlertQueue,
    notification_delivery,
)
from app.services.operation_task_service import OperationTaskService
from app.utils.utils import create_upload_file_from_path
from tests.integration.helpers.notifications import (
    as_recipient,
    drop_notifications,
    latest_notification,
    process_saved,
)
from tests.integration.helpers.services import (
    notification_service,
    operation_task_service,
    unit_node_service,
)
from tests.integration.helpers.tasks import drop_task
from tests.integration.helpers.wait import wait_until

LIVE_ALERT_YAML = "tests/data/yaml/integra/data_pipe_alerts_live.yaml"

pytestmark = pytest.mark.notification


def test_get_notification_settings(
    regular_user, regular_user_token, database, cc
) -> None:
    settings_row = notification_service(
        database, cc, regular_user_token
    ).get_settings()
    logging.info(settings_row.uuid)
    assert settings_row.user_uuid == regular_user.uuid
    assert settings_row.is_scheduled_alert_enable is True
    assert settings_row.is_data_pipe_alert_enable is True
    assert settings_row.is_telegram_alert_enable is True
    assert settings_row.scheduled_notification_time == "16:00"


def test_user_create_makes_notification_settings(extra_user, database) -> None:
    # UserService.create stores the row, the API never relies on get_or_create
    settings_row = NotificationSettingsRepository(database).get_by_user(
        extra_user.uuid
    )
    assert settings_row is not None
    assert settings_row.is_data_pipe_alert_enable is True


def test_update_notification_settings(
    extra_user, extra_user_token, database, cc
) -> None:
    service = notification_service(database, cc, extra_user_token)
    updated = service.update_settings(
        NotificationSettingsUpdate(
            is_scheduled_alert_enable=True,
            scheduled_notification_time="16:00",
            is_data_pipe_alert_enable=True,
            is_telegram_alert_enable=True,
        )
    )
    logging.info(updated.uuid)
    assert updated.user_uuid == extra_user.uuid
    assert updated.is_scheduled_alert_enable is True
    assert updated.scheduled_notification_time == "16:00"
    assert updated.is_data_pipe_alert_enable is True
    assert updated.is_telegram_alert_enable is True

    stored = service.get_settings()
    assert stored.is_telegram_alert_enable is True
    assert stored.scheduled_notification_time == "16:00"


def test_update_notification_settings_invalid_time(
    extra_user_token, database, cc
) -> None:
    service = notification_service(database, cc, extra_user_token)
    with pytest.raises(SchemaValidationError):
        service.update_settings(
            NotificationSettingsUpdate(scheduled_notification_time="25:00")
        )
    assert service.get_settings().scheduled_notification_time == "16:00"


def test_notification_text_by_type() -> None:
    instance_alert = InstanceDailyStateData.model_validate(
        {"errors": [{"count": 4, "message": "disk full"}]}
    )
    instance = instance_alert.table_text
    assert instance_alert.small_text == "Instance has 4 errors"
    several = InstanceDailyStateData.model_validate(
        {
            "errors": [
                {"count": 2, "message": "disk full"},
                {"count": 1, "message": "timeout"},
            ]
        }
    )
    assert several.small_text == "Instance has 3 errors"
    one = InstanceDailyStateData.model_validate(
        {"errors": [{"count": 1, "message": "disk full"}]}
    )
    assert one.small_text == "Instance has 1 error"
    assert instance_alert.big_text is None
    assert "Instance daily summary" in instance
    assert "disk full" in instance
    wrapped = TelegramAlertQueue.text(instance)
    assert wrapped.startswith("\n```text\n")
    assert wrapped.endswith("```")

    summary_alert = UnitDailySummaryData.model_validate(
        {"units": [{"unit_name": "boiler", "error_count": 7}]}
    )
    summary = summary_alert.table_text
    assert summary_alert.small_text == "Unit has 7 errors"
    assert summary_alert.big_text is None
    assert "Unit daily summary" in summary
    assert "boiler" in summary
    assert "7" in summary
    fenced = TelegramAlertQueue.text(summary)
    assert fenced.startswith("\n```text\n")
    assert fenced.endswith("```")

    started = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    for task_type in OperationTaskType:
        alert = OPERATION_TASK_ALERTS[NotificationType(task_type)](
            status=OperationTaskStatus.RUNNING,
            start_datetime=started,
        )
        text = alert.table_text
        assert alert.small_text == f"{alert.task_type.value}: Running"
        assert "```" not in text
        assert alert.title in text
        assert "Operation task" not in text
        assert "Running" in text
        assert "Result" not in text
        assert alert.big_text is None
        wrapped = TelegramAlertQueue.text(text)
        assert wrapped.startswith("\n```text\n")
        assert wrapped.endswith("```")

    full_log = "UNIQUE_DEBUG\n" + ("x" * 400)
    finished_alert = OPERATION_TASK_ALERTS[NotificationType.INTEGRATION_TESTS](
        status=OperationTaskStatus.ERROR,
        start_datetime=started,
        finish_datetime=started + timedelta(seconds=12),
        result=full_log,
    )
    finished = finished_alert.table_text
    assert "Error" in finished
    assert "2026-01-02 03:04:05" in finished
    assert "UNIQUE_DEBUG" not in finished
    assert finished_alert.small_text == "IntegrationTests: Error"
    assert finished_alert.big_text == full_log

    for data, phrase in (
        (
            {"type_value_threshold": "Min", "threshold_min": 1},
            ">= 1",
        ),
        (
            {"type_value_threshold": "Max", "threshold_max": 10},
            "<= 10",
        ),
        (
            {
                "type_value_threshold": "Range",
                "threshold_min": 1,
                "threshold_max": 2,
            },
            "∈ [1, 2]",
        ),
        (
            {
                "type_value_filtering": "WhiteList",
                "filtering_values": ["a", "b"],
            },
            "is a, b",
        ),
        (
            {
                "type_value_filtering": "BlackList",
                "filtering_values": ["a", "b"],
            },
            "not is a, b",
        ),
        ({}, "any"),
    ):
        pipe = DataPipeAlertData.model_validate({"value": "x", **data})
        text = pipe.table_text
        assert phrase in pipe.small_text
        assert pipe.big_text is None
        assert "```" not in text
        assert "Data pipe alert" in text
        assert phrase in text
        named = DataPipeAlertData.model_validate(
            {"value": "x", "unit_name": "boiler", **data}
        ).table_text
        assert "boiler" in named
        fenced = TelegramAlertQueue.text(text)
        assert fenced.startswith("\n```text\n")
        assert fenced.endswith("```")


def test_integration_tests_big_text_is_stored(
    admin_user, admin_user_token, database, cc
) -> None:
    full_log = "UNIQUE_STORED\n" + ("y" * 400)
    owned = {
        row.uuid
        for row in database.query(Notification)
        .filter(Notification.user_uuid == admin_user.uuid)
        .all()
    }
    task = operation_task_service(database, admin_user_token).create(
        OperationTaskCreate(task_type=OperationTaskType.INTEGRATION_TESTS)
    )
    finished = OperationTaskService._finish(
        OperationTaskRepository(database),
        task.uuid,
        OperationTaskStatus.ERROR,
        full_log,
    )
    OperationTaskService._record_alert(database, finished)
    service = notification_service(database, cc, admin_user_token)
    pending = (
        database.query(Notification)
        .filter(
            Notification.user_uuid == admin_user.uuid,
            Notification.is_processed.is_(False),
        )
        .all()
    )
    pending = [row for row in pending if row.uuid not in owned]
    process_saved(service, pending)
    stored = [service.get(row.uuid) for row in pending]
    saved = next(row for row in stored if row.big_text)
    try:
        assert saved.big_text == full_log
        assert "UNIQUE_STORED" not in saved.table_text
        assert saved.small_text == "IntegrationTests: Error"
        read = NotificationRead(**saved.dict())
        assert read.small_text == saved.small_text
        assert read.table_text == saved.table_text
        assert read.big_text == full_log
        dumped = read.model_dump()
        assert "data" not in dumped
        assert "text" not in dumped
    finally:
        drop_notifications(database, stored)
        drop_task(database, task.uuid)


def test_telegram_alert_send_rate() -> None:
    queue = TelegramAlertQueue(user_interval=1, instance_rate=20)
    queue.ready.set()
    gap = 1 / 20

    queue.enqueue("alpha", "a0")
    queue.enqueue("alpha", "a1")
    queue.enqueue("beta", "b")

    chat, _text = queue._ready_message(0)
    assert chat == "alpha"
    queue._mark_sent("alpha", 0)
    assert queue._ready_message(gap / 2) is None
    assert queue._seconds_until_next(gap / 2) == gap / 2

    chat, _text = queue._ready_message(gap)
    assert chat == "beta"
    queue._mark_sent("beta", gap)
    assert queue._ready_message(gap * 2) is None

    chat, _text = queue._ready_message(1)
    assert chat == "alpha"
    assert queue._ready_message(1) is None


def test_notification_stream(
    regular_user, regular_user_token, database, cc
) -> None:
    url = f"{settings.pu_link_prefix_and_v1}/notifications/stream"
    rejected = httpx.get(
        url,
        headers={"x-auth-token": "not-a-token"},
        timeout=10,
    )
    assert rejected.status_code == 403

    notification = None
    task = None
    try:
        with httpx.stream(
            "GET",
            url,
            headers={
                "x-auth-token": regular_user_token,
                "accept": "text/event-stream",
            },
            timeout=httpx.Timeout(20.0, read=20.0),
        ) as response:
            assert response.status_code == 200
            assert response.headers["content-type"].startswith(
                "text/event-stream"
            )
            lines = response.iter_lines()
            assert next(lines) == ": connected"
            # The handler yields the handshake before it blocks on the stream
            time.sleep(0.5)
            task = operation_task_service(
                database, regular_user_token
            ).create(
                OperationTaskCreate(
                    task_type=OperationTaskType.UPDATE_REGISTRY
                )
            )
            service = notification_service(database, cc, regular_user_token)
            notification = latest_notification(database, regular_user.uuid)
            process_saved(service, [notification])
            notification = service.get(notification.uuid)

            message = None
            expected = str(notification.uuid)
            for line in lines:
                if not line.startswith("data: "):
                    continue
                payload = json.loads(line.removeprefix("data: "))
                if payload["uuid"] == expected:
                    message = payload
                    break
        assert message is not None
        assert message["uuid"] == str(notification.uuid)
        assert message["type"] == NotificationType.UPDATE_REGISTRY.value
        assert "is_processed" not in message
        assert "data" not in message
        assert "Update Registry" in message["table_text"]
        assert message["small_text"]
        assert "text" not in message
    finally:
        if notification is not None:
            drop_notifications(database, [notification])
        if task is not None:
            drop_task(database, task.uuid)


@pytest.mark.datapipe
async def test_data_pipe_alert_live(
    running_units, recipient_service, regular_user_token, database, cc
) -> None:
    """Unit emulator -> MQTT -> data pipe -> notifications table -> backend job"""
    service = unit_node_service(database, cc, regular_user_token)
    _, nodes = service.list(
        UnitNodeFilter.unlimited(
            unit_uuid=running_units.chain_sink_unit.uuid,
            type=[UnitNodeTypeEnum.OUTPUT],
        )
    )
    node = nodes[0]
    started = datetime.now(UTC)
    created = []
    try:
        await service.update(
            node.uuid, UnitNodeUpdate(is_data_pipe_active=True)
        )
        await service.set_data_pipe_config(
            node.uuid, (await create_upload_file_from_path(LIVE_ALERT_YAML))
        )

        def alert_arrived() -> bool:
            _, notifications = recipient_service.list(
                NotificationFilter.unlimited(
                    type=[NotificationType.DATA_PIPE_ALERT.value]
                )
            )
            created[:] = [
                item
                for item in notifications
                if item.data["unit_node_uuid"] == str(node.uuid)
                and _aware(item.create_datetime) >= started
            ]
            return bool(created)

        wait_until(
            alert_arrived,
            timeout=60,
            interval=2,
            message="data pipe alert did not reach the backend",
            session=database,
        )

        data = created[0].data
        assert data["type_value_threshold"] == "Min"
        assert data["threshold_min"] == 0
        assert data["topic_name"] == node.topic_name
        assert data["unit_uuid"] == str(node.unit_uuid)
        assert data["unit_name"] == running_units.chain_sink_unit.name
        assert float(data["value"]) >= 0
        alert = created[0]
        assert running_units.chain_sink_unit.name in alert.small_text
        assert running_units.chain_sink_unit.name in alert.table_text
        assert "Data pipe alert" in alert.table_text
        assert alert.big_text is None
    finally:
        await service.update(
            node.uuid, UnitNodeUpdate(is_data_pipe_active=False)
        )
        recipient_service.update_settings(
            NotificationSettingsUpdate(is_data_pipe_alert_enable=False)
        )
        _, leftovers = recipient_service.list(
            NotificationFilter.unlimited(
                type=[NotificationType.DATA_PIPE_ALERT.value]
            )
        )
        drop_notifications(
            database,
            [
                item
                for item in leftovers
                if item.data["unit_node_uuid"] == str(node.uuid)
            ],
        )


def test_get_notification(
    crud_notification, regular_user_token, database, cc
) -> None:
    service = notification_service(database, cc, regular_user_token)
    assert service.get(crud_notification.uuid).uuid == crud_notification.uuid


def test_get_notification_not_target(
    crud_notification, extra_user_token, database, cc
) -> None:
    service = notification_service(database, cc, extra_user_token)
    with pytest.raises(NoAccessError):
        service.get(crud_notification.uuid)


def test_get_many_notification(
    crud_notification, regular_user, regular_user_token, database, cc
) -> None:
    service = notification_service(database, cc, regular_user_token)
    count, notifications = service.list(NotificationFilter.unlimited())
    assert count >= 1
    assert any(item.uuid == crud_notification.uuid for item in notifications)
    assert all(item.user_uuid == regular_user.uuid for item in notifications)

    count, notifications = service.list(
        NotificationFilter.unlimited(
            type=[NotificationType.UPDATE_REGISTRY.value],
            is_read=False,
        )
    )
    assert any(item.uuid == crud_notification.uuid for item in notifications)
    assert all(
        item.type == NotificationType.UPDATE_REGISTRY.value
        for item in notifications
    )
    assert all(item.is_read is False for item in notifications)

    count, notifications = service.list(
        NotificationFilter.unlimited(
            type=[NotificationType.UNIT_DAILY_SUMMARY.value]
        )
    )
    assert all(item.uuid != crud_notification.uuid for item in notifications)


def test_list_notifications_only_own(
    crud_notification, extra_user_token, database, cc
) -> None:
    service = notification_service(database, cc, extra_user_token)
    _count, notifications = service.list(NotificationFilter.unlimited())
    assert all(item.uuid != crud_notification.uuid for item in notifications)


def test_mark_notification_read(
    crud_notification, regular_user_token, database, cc
) -> None:
    service = notification_service(database, cc, regular_user_token)
    read = service.mark_read(crud_notification.uuid)
    assert read.is_read is True
    assert read.read_datetime is not None

    again = service.mark_read(crud_notification.uuid)
    assert again.read_datetime == read.read_datetime


def test_mark_all_notifications_read(
    crud_notification, regular_user, regular_user_token, database, cc
) -> None:
    task = operation_task_service(database, regular_user_token).create(
        OperationTaskCreate(task_type=OperationTaskType.SCAN_INSTANCE)
    )
    service = notification_service(database, cc, regular_user_token)
    second = latest_notification(database, regular_user.uuid)
    process_saved(service, [second])
    try:
        marked = service.mark_all_read()
        assert marked >= 2
        _count, notifications = service.list(NotificationFilter.unlimited())
        assert any(
            item.uuid == crud_notification.uuid for item in notifications
        )
        assert all(item.is_read is True for item in notifications)
        assert service.mark_all_read() == 0
    finally:
        drop_notifications(database, [second])
        drop_task(database, task.uuid)


def test_notification_anonymous(crud_notification, database, cc) -> None:
    service = notification_service(database, cc, None)
    with pytest.raises(NoAccessError):
        service.get_settings()
    with pytest.raises(NoAccessError):
        service.update_settings(
            NotificationSettingsUpdate(is_telegram_alert_enable=True)
        )
    with pytest.raises(NoAccessError):
        service.get(crud_notification.uuid)
    with pytest.raises(NoAccessError):
        service.list(NotificationFilter())
    with pytest.raises(NoAccessError):
        service.mark_read(crud_notification.uuid)
    with pytest.raises(NoAccessError):
        service.mark_all_read()
    with pytest.raises(NoAccessError):
        service.access_service.authorization.check_access([AgentType.USER])


def test_create_scheduled_instance_state(
    admin_user, admin_user_token, database, cc
) -> None:
    created = []
    with as_recipient(database, cc, admin_user, admin_user_token) as service:
        try:
            service.update_settings(
                NotificationSettingsUpdate(
                    is_scheduled_alert_enable=True,
                    scheduled_notification_time=_scheduled_now(),
                )
            )
            deliveries = _generate_scheduled(service, created)

            instance_alerts = [
                item
                for item in deliveries
                if item.type == NotificationType.INSTANCE_DAILY_STATE.value
            ]
            assert len(instance_alerts) == 1
            errors = instance_alerts[0].data["errors"]
            assert len(errors) <= 3
            assert all(
                "count" in item and "message" in item for item in errors
            )
            assert instance_alerts[0].is_processed is True
            total = sum(item["count"] for item in errors)
            noun = "error" if total == 1 else "errors"
            assert (
                instance_alerts[0].small_text
                == f"Instance has {total} {noun}"
            )
            assert instance_alerts[0].table_text
            _, notifications = service.list(
                NotificationFilter.unlimited(
                    type=[NotificationType.INSTANCE_DAILY_STATE.value]
                )
            )
            assert instance_alerts[0].uuid in {
                item.uuid for item in notifications
            }
        finally:
            drop_notifications(database, created)


def test_create_scheduled_unit_summary(
    live_units, regular_user, regular_user_token, database, cc
) -> None:
    created = []
    unit = live_units.universal_manual_unit
    with as_recipient(
        database, cc, regular_user, regular_user_token
    ) as service:
        try:
            service.update_settings(
                NotificationSettingsUpdate(
                    is_scheduled_alert_enable=True,
                    scheduled_notification_time=_scheduled_now(),
                )
            )
            error_text = f"integration alert {uuid_pkg.uuid4()}"
            critical_text = f"integration critical {uuid_pkg.uuid4()}"
            info_text = f"integration info {uuid_pkg.uuid4()}"
            log_time = datetime.now(UTC).replace(tzinfo=None) - timedelta(
                minutes=1
            )
            expiration = datetime.now(UTC) + timedelta(
                seconds=settings.pu_unit_log_expiration
            )
            UnitLogRepository(cc).bulk_create(
                [
                    UnitLog(
                        uuid=uuid_pkg.uuid4(),
                        level=LogLevel.ERROR,
                        unit_uuid=unit.uuid,
                        text=error_text,
                        create_datetime=log_time,
                        expiration_datetime=expiration,
                    ),
                    UnitLog(
                        uuid=uuid_pkg.uuid4(),
                        level=LogLevel.ERROR,
                        unit_uuid=unit.uuid,
                        text=error_text,
                        create_datetime=log_time + timedelta(seconds=1),
                        expiration_datetime=expiration,
                    ),
                    UnitLog(
                        uuid=uuid_pkg.uuid4(),
                        level=LogLevel.CRITICAL,
                        unit_uuid=unit.uuid,
                        text=critical_text,
                        create_datetime=log_time + timedelta(seconds=2),
                        expiration_datetime=expiration,
                    ),
                    UnitLog(
                        uuid=uuid_pkg.uuid4(),
                        level=LogLevel.INFO,
                        unit_uuid=unit.uuid,
                        text=info_text,
                        create_datetime=log_time + timedelta(seconds=3),
                        expiration_datetime=expiration,
                    ),
                ]
            )

            deliveries = _generate_scheduled(service, created)

            assert all(
                item.type != NotificationType.INSTANCE_DAILY_STATE.value
                for item in deliveries
            )
            summary = next(
                item
                for item in deliveries
                if item.type == NotificationType.UNIT_DAILY_SUMMARY.value
            )
            row = next(
                item
                for item in summary.data["units"]
                if item["unit_name"] == unit.name
            )
            assert row["error_count"] >= 3
            assert len(summary.data["units"]) <= 10
            assert set(row) == {"unit_name", "error_count"}
            assert summary.is_processed is True
            total = sum(item["error_count"] for item in summary.data["units"])
            assert summary.small_text == f"Unit has {total} errors"
            assert unit.name in summary.table_text
        finally:
            drop_notifications(database, created)


def _generate_scheduled(service, created: list) -> list[Notification]:
    """Runs the scheduler and returns the signed-in user's notifications.

    Every row from this run is kept in created, including other recipients
    of the same minute, so the test can delete what it caused.
    """
    rows = service.generate_scheduled()
    created.extend(rows)
    process_saved(service, rows)
    user_uuid = service.access_service.current_agent.uuid
    return [
        service.get(item.uuid) for item in rows if item.user_uuid == user_uuid
    ]


def _stream_has(
    user_uuid: uuid_pkg.UUID, notification_uuid: uuid_pkg.UUID
) -> bool:
    async def has() -> bool:
        session = get_redis_session()
        redis = await anext(session)
        try:
            messages = await redis.xrevrange(
                notification_delivery.stream_name(user_uuid),
                count=100,
            )
        finally:
            await session.aclose()
        needle = str(notification_uuid)
        return any(
            needle in fields[notification_delivery.EVENT]
            for _message_id, fields in messages
        )

    return asyncio.run(has())


def _upcoming_slot() -> datetime:
    """The next scheduler minute, with time left to commit the settings"""
    now = datetime.now(UTC)
    skip = 2 if now.second >= 50 else 1
    return (now + timedelta(minutes=skip)).replace(second=0, microsecond=0)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def test_live_scheduled_alerts_reach_recipient(
    live_units, regular_user, regular_user_token, database, cc
) -> None:
    """The running backend sends the admin and unit summaries to this user.

    Data pipe alerts are covered by test_data_pipe_alert_live. Instance state
    is admin-only, so the recipient is an admin until the scheduler minute.
    """
    repository = UserRepository(db=database)
    previous_role = regular_user.role
    regular_user.role = UserRole.ADMIN
    repository.update(regular_user.uuid, regular_user)
    slot = _upcoming_slot()
    found: list[Notification] = []
    try:
        with as_recipient(
            database, cc, regular_user, regular_user_token
        ) as service:
            service.update_settings(
                NotificationSettingsUpdate(
                    is_scheduled_alert_enable=True,
                    scheduled_notification_time=slot.strftime("%H:%M"),
                    is_telegram_alert_enable=True,
                )
            )

            def arrived() -> bool:
                _, rows = service.list(NotificationFilter.unlimited())
                found[:] = [
                    item
                    for item in rows
                    if _aware(item.create_datetime) >= slot
                    and item.type
                    in (
                        NotificationType.INSTANCE_DAILY_STATE.value,
                        NotificationType.UNIT_DAILY_SUMMARY.value,
                    )
                ]
                types = {item.type for item in found}
                return {
                    NotificationType.INSTANCE_DAILY_STATE.value,
                    NotificationType.UNIT_DAILY_SUMMARY.value,
                } <= types

            wait_until(
                arrived,
                timeout=120,
                interval=2,
                message="scheduled alerts did not reach the recipient",
                session=database,
            )
    finally:
        regular_user.role = previous_role
        repository.update(regular_user.uuid, regular_user)
        drop_notifications(database, found)


def _scheduled_now() -> str:
    """HH:MM of now, waits out the end of a minute so creation sees the same one"""
    now = datetime.now(UTC)
    if now.second > 50:
        time.sleep(60 - now.second)
        now = datetime.now(UTC)
    return now.strftime("%H:%M")
