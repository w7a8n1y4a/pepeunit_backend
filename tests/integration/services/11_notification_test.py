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
from app.configs.errors import NoAccessError, NotificationError
from app.domain.notification_model import Notification
from app.dto.clickhouse.log import UnitLog
from app.dto.enum import (
    AgentType,
    LogLevel,
    NotificationType,
    UnitNodeTypeEnum,
    UserRole,
)
from app.repositories.notification_settings_repository import (
    NotificationSettingsRepository,
)
from app.repositories.unit_log_repository import UnitLogRepository
from app.repositories.user_repository import UserRepository
from app.schemas.pydantic.notification import (
    NotificationFilter,
    NotificationIn,
    NotificationRead,
    NotificationSettingsUpdate,
)
from app.schemas.pydantic.unit_node import UnitNodeFilter, UnitNodeUpdate
from app.services.notification_delivery import NotificationMessage
from app.utils.utils import create_upload_file_from_path
from tests.integration.helpers.notifications import (
    as_recipient,
    data_pipe_alert,
    data_pipe_stream,
    drop_notifications,
)
from tests.integration.helpers.services import (
    notification_service,
    unit_node_service,
    unit_service,
)
from tests.integration.helpers.wait import wait_until

LIVE_ALERT_YAML = "tests/data/yaml/integra/data_pipe_alerts_live.yaml"


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


def test_create_data_pipe_alert(
    crud_notification,
    regular_user,
    regular_user_token,
    alert_node,
    database,
    cc,
) -> None:
    logging.info(crud_notification.uuid)
    unit = unit_service(database, cc, regular_user_token).get(
        alert_node.unit_uuid
    )

    assert crud_notification.type == NotificationType.DATA_PIPE_ALERT.value
    assert crud_notification.user_uuid == regular_user.uuid
    assert crud_notification.is_read is False
    assert crud_notification.read_datetime is None

    data = crud_notification.data
    assert data["unit_node_uuid"] == str(alert_node.uuid)
    assert data["unit_uuid"] == str(alert_node.unit_uuid)
    assert data["unit_name"] == unit.name
    assert data["topic_name"] == alert_node.topic_name
    assert data["value"] == "12.5"
    assert data["type_value_threshold"] == "Max"
    assert data["threshold_max"] == 10
    assert data["threshold_min"] is None
    assert data["type_value_filtering"] is None
    assert data["filtering_values"] is None


def test_data_pipe_alert_rules(
    recipient_service, alert_node, regular_user, database
) -> None:
    rules = [
        (
            {
                "type_value_threshold": "Range",
                "threshold_min": "1",
                "threshold_max": "10",
            },
            {
                "type_value_threshold": "Range",
                "threshold_min": 1,
                "threshold_max": 10,
                "type_value_filtering": None,
                "filtering_values": None,
            },
        ),
        (
            {
                "type_value_threshold": "Min",
                "threshold_min": "3",
                "threshold_max": None,
            },
            {
                "type_value_threshold": "Min",
                "threshold_min": 3,
                "threshold_max": None,
                "type_value_filtering": None,
                "filtering_values": None,
            },
        ),
        (
            {
                "value": "overheat",
                "type_value_threshold": None,
                "threshold_max": None,
                "type_value_filtering": "BlackList",
                "filtering_values": '["overheat", "fire"]',
            },
            {
                "type_value_threshold": None,
                "threshold_min": None,
                "threshold_max": None,
                "type_value_filtering": "BlackList",
                "filtering_values": ["overheat", "fire"],
            },
        ),
    ]
    created = []
    try:
        for fields, expected in rules:
            incoming = data_pipe_alert(alert_node, regular_user, **fields)
            notification = _pipe(recipient_service, incoming)
            created.append(notification)

            data = notification.data
            assert data["value"] == incoming.data.value
            for key, value in expected.items():
                assert data[key] == value
    finally:
        drop_notifications(database, created)


def test_data_pipe_alert_invalid_rule(
    recipient_service, alert_node, regular_user
) -> None:
    invalid_rules = [
        {"type_value_threshold": None, "threshold_max": None},
        {"type_value_threshold": None},
        {"threshold_max": "high"},
        {"threshold_max": "nan"},
        {"type_value_threshold": None, "threshold_min": "1"},
        {"type_value_threshold": "Min", "threshold_max": None},
        {"type_value_threshold": "Min"},
        {
            "type_value_threshold": "Range",
            "threshold_max": None,
            "threshold_min": "1",
        },
        {"type_value_threshold": "Range"},
        {
            "type_value_threshold": None,
            "type_value_filtering": "WhiteList",
        },
        {
            "type_value_threshold": None,
            "type_value_filtering": "BlackList",
            "filtering_values": "[]",
        },
        {
            "type_value_threshold": None,
            "type_value_filtering": "BlackList",
            "filtering_values": "not json",
        },
        {
            "type_value_threshold": None,
            "type_value_filtering": "BlackList",
            "filtering_values": '"overheat"',
        },
        {"type_value_threshold": "Sideways"},
        {"value": None},
    ]
    count_before, _notifications = recipient_service.list(
        NotificationFilter.unlimited()
    )
    for fields in invalid_rules:
        fields_on_stream = data_pipe_stream(alert_node, regular_user, **fields)
        with pytest.raises(NotificationError):
            NotificationIn.from_stream(fields_on_stream)

    count_after, _notifications = recipient_service.list(
        NotificationFilter.unlimited()
    )
    assert count_after == count_before


def test_data_pipe_alert_unknown_user(
    recipient_service, alert_node, regular_user
) -> None:
    count_before, _notifications = recipient_service.list(
        NotificationFilter.unlimited()
    )
    incoming = data_pipe_alert(alert_node, regular_user)
    incoming.user_uuid = uuid_pkg.uuid4()
    assert _pipe(recipient_service, incoming) is None
    with pytest.raises(NotificationError):
        NotificationIn.from_stream({"value": "12.5"})
    count_after, _notifications = recipient_service.list(
        NotificationFilter.unlimited()
    )
    assert count_after == count_before


def test_data_pipe_alert_recipients(
    recipient_service,
    alert_node,
    regular_user,
    extra_user,
    extra_user_token,
    database,
    cc,
) -> None:
    # extra_user enabled the alerts but is not the node creator
    with as_recipient(
        database, cc, extra_user, extra_user_token
    ) as extra_service:
        extra_service.update_settings(
            NotificationSettingsUpdate(is_data_pipe_alert_enable=True)
        )
        before_extra, _rows = extra_service.list(
            NotificationFilter.unlimited()
        )
        notification = _pipe(
            recipient_service, data_pipe_alert(alert_node, regular_user)
        )
        try:
            assert notification.user_uuid == regular_user.uuid
            after_extra, _rows = extra_service.list(
                NotificationFilter.unlimited()
            )
            assert after_extra == before_extra
        finally:
            drop_notifications(database, [notification])

    # the owner disabled the alerts
    recipient_service.update_settings(
        NotificationSettingsUpdate(is_data_pipe_alert_enable=False)
    )
    before, _rows = recipient_service.list(NotificationFilter.unlimited())
    assert (
        _pipe(recipient_service, data_pipe_alert(alert_node, regular_user))
        is None
    )
    after, _rows = recipient_service.list(NotificationFilter.unlimited())
    assert after == before


def test_data_pipe_alert_delivery(
    recipient_service, alert_node, regular_user, database
) -> None:
    recipient_service.update_settings(
        NotificationSettingsUpdate(is_telegram_alert_enable=True)
    )
    notification = _pipe(
        recipient_service, data_pipe_alert(alert_node, regular_user)
    )
    try:
        assert notification.user_uuid == regular_user.uuid
        assert (
            recipient_service.get_settings().is_telegram_alert_enable is True
        )

        read = NotificationRead(**notification.dict())
        assert read.uuid == notification.uuid
        assert read.type == NotificationType.DATA_PIPE_ALERT
        assert read.user_uuid == regular_user.uuid
        assert read.is_read is False
        assert read.data["topic_name"] == alert_node.topic_name

        text = NotificationMessage.text(notification)
        assert alert_node.topic_name in text
        assert "12.5" in text
        assert "above 10" in text
    finally:
        drop_notifications(database, [notification])


def test_telegram_text_by_type(regular_user) -> None:
    def notification(
        notification_type: NotificationType, data: dict
    ) -> Notification:
        return Notification(
            create_datetime=datetime.now(UTC),
            type=notification_type.value,
            data=data,
            user_uuid=regular_user.uuid,
        )

    instance = NotificationMessage.text(
        notification(
            NotificationType.INSTANCE_DAILY_STATE,
            {"errors": [{"count": 4, "message": "disk full"}]},
        )
    )
    assert instance.startswith("\n```text\n")
    assert instance.endswith("```")
    assert "Instance daily summary" in instance
    assert "disk full" in instance

    unavailable = NotificationMessage.text(
        notification(
            NotificationType.INSTANCE_DAILY_STATE,
            {"errors": None},
        )
    )
    assert "Instance daily summary" in unavailable
    assert "Loki did not return data" in unavailable
    assert "0" not in unavailable

    summary = NotificationMessage.text(
        notification(
            NotificationType.UNIT_DAILY_SUMMARY,
            {"units": [{"unit_name": "boiler", "error_count": 7}]},
        )
    )
    assert summary.startswith("\n```text\n")
    assert summary.endswith("```")
    assert "Unit daily summary" in summary
    assert "boiler" in summary
    assert "7" in summary

    for data, phrase in (
        (
            {"type_value_threshold": "Min", "threshold_min": 1},
            "below 1",
        ),
        (
            {
                "type_value_threshold": "Range",
                "threshold_min": 1,
                "threshold_max": 2,
            },
            "outside [1, 2]",
        ),
        (
            {
                "type_value_filtering": "WhiteList",
                "filtering_values": ["a", "b"],
            },
            "is not one of: a, b",
        ),
        (
            {
                "type_value_filtering": "BlackList",
                "filtering_values": ["a", "b"],
            },
            "is one of: a, b",
        ),
    ):
        text = NotificationMessage.text(
            notification(
                NotificationType.DATA_PIPE_ALERT,
                {"value": "x", **data},
            )
        )
        assert phrase in text


def test_notification_stream(
    recipient_service, alert_node, regular_user, regular_user_token, database
) -> None:
    url = f"{settings.pu_link_prefix_and_v1}/notifications/stream"
    rejected = httpx.get(
        url,
        headers={"x-auth-token": "not-a-token"},
        timeout=10,
    )
    assert rejected.status_code == 403

    notification = None
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
            notification = _pipe(
                recipient_service, data_pipe_alert(alert_node, regular_user)
            )

            message = None
            for line in lines:
                if not line.startswith("data: "):
                    continue
                message = json.loads(line.removeprefix("data: "))
                break
        assert message is not None
        assert message["uuid"] == str(notification.uuid)
        assert message["type"] == NotificationType.DATA_PIPE_ALERT.value
        assert message["data"]["topic_name"] == alert_node.topic_name
    finally:
        if notification is not None:
            drop_notifications(database, [notification])


@pytest.mark.datapipe
async def test_data_pipe_alert_live(
    running_units, recipient_service, regular_user_token, database, cc
) -> None:
    """Unit emulator -> MQTT -> data pipe -> Redis stream -> backend consumer"""
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
                if item.data.get("unit_node_uuid") == str(node.uuid)
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
        assert data["threshold_min"] == 1000
        assert data["topic_name"] == node.topic_name
        assert data["unit_uuid"] == str(node.unit_uuid)
        assert float(data["value"]) < 1000
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
            type=[NotificationType.DATA_PIPE_ALERT.value],
            is_read=False,
        )
    )
    assert any(item.uuid == crud_notification.uuid for item in notifications)
    assert all(
        item.type == NotificationType.DATA_PIPE_ALERT.value
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
    crud_notification, recipient_service, alert_node, regular_user, database
) -> None:
    notification = _pipe(
        recipient_service,
        data_pipe_alert(alert_node, regular_user, value="20"),
    )
    try:
        marked = recipient_service.mark_all_read()
        assert marked >= 2
        _count, notifications = recipient_service.list(
            NotificationFilter.unlimited()
        )
        assert any(
            item.uuid == crud_notification.uuid for item in notifications
        )
        assert all(item.is_read is True for item in notifications)
        assert recipient_service.mark_all_read() == 0
    finally:
        drop_notifications(database, [notification])


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
            deliveries = _create_scheduled_for_current(service)
            created.extend(deliveries)
            assert all(
                item.user_uuid == admin_user.uuid for item in deliveries
            )

            instance_alerts = [
                item
                for item in created
                if item.type == NotificationType.INSTANCE_DAILY_STATE.value
            ]
            assert len(instance_alerts) == 1
            errors = instance_alerts[0].data["errors"]
            assert errors is None or (
                isinstance(errors, list)
                and len(errors) <= 3
                and all(
                    "count" in item and "message" in item for item in errors
                )
            )

            # the same minute does not send a second copy
            assert _create_scheduled_for_current(service) == []
            instance_alerts[0].create_datetime = datetime.now(UTC) - timedelta(
                minutes=2
            )
            service.notification_repository.update(
                instance_alerts[0].uuid, instance_alerts[0]
            )
            again = _create_scheduled_for_current(service)
            created.extend(again)
            assert any(
                item.type == NotificationType.INSTANCE_DAILY_STATE.value
                for item in again
            )
            created_ids = {
                item.uuid
                for item in created
                if item.type == NotificationType.INSTANCE_DAILY_STATE.value
            }
            _, notifications = service.list(
                NotificationFilter.unlimited(
                    type=[NotificationType.INSTANCE_DAILY_STATE.value]
                )
            )
            assert created_ids <= {item.uuid for item in notifications}
            assert len(created_ids) == 2
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

            deliveries = _create_scheduled_for_current(service)
            created.extend(deliveries)

            assert all(
                item.user_uuid == regular_user.uuid for item in deliveries
            )
            assert all(
                item.type != NotificationType.INSTANCE_DAILY_STATE.value
                for item in deliveries
            )
            summary = next(
                item
                for item in created
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

            # the same minute does not send a second copy
            assert _create_scheduled_for_current(service) == []
            summary.create_datetime = datetime.now(UTC) - timedelta(minutes=2)
            service.notification_repository.update(summary.uuid, summary)
            again = _create_scheduled_for_current(service)
            created.extend(again)
            assert any(
                item.type == NotificationType.UNIT_DAILY_SUMMARY.value
                for item in again
            )
        finally:
            drop_notifications(database, created)


def _pipe(service, incoming):
    return asyncio.run(service.notification_pipe(incoming))


def _create_scheduled_for_current(service):
    """Creates notifications only for the signed-in user"""
    user = service.access_service.current_agent
    incoming = service.due_scheduled(datetime.now(UTC), user.uuid)
    return [
        row for item in incoming if (row := _pipe(service, item)) is not None
    ]


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
