import asyncio
import json
import logging
import time
import uuid as uuid_pkg
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app import settings
from app.configs.errors import NoAccessError, NotificationError
from app.domain.notification_model import Notification
from app.dto.clickhouse.log import UnitLog
from app.dto.enum import LogLevel, NotificationType, UnitNodeTypeEnum
from app.repositories.notification_settings_repository import (
    NotificationSettingsRepository,
)
from app.repositories.unit_log_repository import UnitLogRepository
from app.schemas.pydantic.notification import (
    NotificationFilter,
    NotificationSettingsUpdate,
)
from app.schemas.pydantic.unit_node import UnitNodeFilter, UnitNodeUpdate
from app.services.notification_delivery import (
    deliver,
    notification_payload,
    telegram_text,
)
from app.utils.utils import create_upload_file_from_path
from tests.integration.helpers.notifications import (
    as_recipient,
    data_pipe_event,
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
    with pytest.raises(NotificationError):
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
    assert crud_notification.target_user_uuid == regular_user.uuid
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
    recipient_service, alert_node, database
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
            event = data_pipe_event(alert_node, **fields)
            event = {
                key: value for key, value in event.items() if value is not None
            }
            deliveries = recipient_service.create_data_pipe_alerts(event)
            assert len(deliveries) == 1
            created.append(deliveries[0].notification)

            data = deliveries[0].notification.data
            assert data["value"] == event["value"]
            for key, value in expected.items():
                assert data[key] == value
    finally:
        drop_notifications(database, created)


def test_data_pipe_alert_invalid_rule(recipient_service, alert_node) -> None:
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
    for fields in invalid_rules:
        event = data_pipe_event(alert_node, **fields)
        event = {
            key: value for key, value in event.items() if value is not None
        }
        assert recipient_service.create_data_pipe_alerts(event) == []

    count, _notifications = recipient_service.list(
        NotificationFilter.unlimited()
    )
    assert count == 0


def test_data_pipe_alert_unknown_node(recipient_service, alert_node) -> None:
    unknown = data_pipe_event(alert_node, unit_node_uuid=str(uuid_pkg.uuid4()))
    assert recipient_service.create_data_pipe_alerts(unknown) == []
    assert recipient_service.create_data_pipe_alerts({"value": "12.5"}) == []
    count, _notifications = recipient_service.list(
        NotificationFilter.unlimited()
    )
    assert count == 0


def test_data_pipe_alert_recipients(
    recipient_service,
    alert_node,
    regular_user,
    extra_user,
    extra_user_token,
    database,
    cc,
) -> None:
    # extra_user enabled the alerts but has no permission on the node
    with as_recipient(
        database, cc, extra_user, extra_user_token
    ) as extra_service:
        extra_service.update_settings(
            NotificationSettingsUpdate(is_data_pipe_alert_enable=True)
        )
        deliveries = recipient_service.create_data_pipe_alerts(
            data_pipe_event(alert_node)
        )
        try:
            assert [item.user_uuid for item in deliveries] == [
                regular_user.uuid
            ]
            assert extra_service.list(NotificationFilter.unlimited())[0] == 0
        finally:
            drop_notifications(
                database, [item.notification for item in deliveries]
            )

    # the owner disabled the alerts
    recipient_service.update_settings(
        NotificationSettingsUpdate(is_data_pipe_alert_enable=False)
    )
    assert (
        recipient_service.create_data_pipe_alerts(data_pipe_event(alert_node))
        == []
    )
    assert recipient_service.list(NotificationFilter.unlimited())[0] == 0


def test_data_pipe_alert_delivery(
    recipient_service, alert_node, regular_user, database
) -> None:
    recipient_service.update_settings(
        NotificationSettingsUpdate(is_telegram_alert_enable=True)
    )
    deliveries = recipient_service.create_data_pipe_alerts(
        data_pipe_event(alert_node)
    )
    try:
        delivery = deliveries[0]
        assert delivery.user_uuid == regular_user.uuid
        assert delivery.telegram_chat_id == regular_user.telegram_chat_id
        assert delivery.is_telegram_alert_enable is True
        assert delivery.push_sse is True

        payload = notification_payload(delivery.notification)
        assert payload["uuid"] == str(delivery.notification.uuid)
        assert payload["type"] == NotificationType.DATA_PIPE_ALERT.value
        assert payload["target_user_uuid"] == str(regular_user.uuid)
        assert payload["is_read"] is False
        assert payload["data"]["topic_name"] == alert_node.topic_name

        text = telegram_text(delivery.notification)
        assert alert_node.topic_name in text
        assert "12.5" in text
        assert "above 10" in text
    finally:
        drop_notifications(
            database, [item.notification for item in deliveries]
        )


def test_telegram_text_by_type(regular_user) -> None:
    def notification(
        notification_type: NotificationType, data: dict
    ) -> Notification:
        return Notification(
            create_datetime=datetime.now(UTC),
            type=notification_type.value,
            data=data,
            target_user_uuid=regular_user.uuid,
        )

    instance = telegram_text(
        notification(
            NotificationType.INSTANCE_DAILY_STATE,
            {
                "entities": {
                    "user_count": 3,
                    "repository_registry_count": 1,
                    "repo_count": 1,
                    "unit_count": 1,
                    "unit_node_count": 1,
                    "unit_node_edge_count": 1,
                },
                "errors": [{"count": 4, "message": "disk full"}],
            },
        )
    )
    assert "Instance metrics" in instance
    assert "User" in instance
    assert "Backend logs" in instance
    assert "disk full" in instance

    summary = telegram_text(
        notification(
            NotificationType.UNIT_DAILY_SUMMARY,
            {"units": [{"unit_name": "boiler", "error_count": 7}]},
        )
    )
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
        text = telegram_text(
            notification(
                NotificationType.DATA_PIPE_ALERT,
                {"value": "x", **data},
            )
        )
        assert phrase in text


def test_notification_stream(
    recipient_service, alert_node, regular_user_token, database
) -> None:
    url = f"{settings.pu_link_prefix_and_v1}/notifications/stream"
    rejected = httpx.get(
        url,
        headers={"x-auth-token": "not-a-token"},
        timeout=10,
    )
    assert rejected.status_code == 403

    deliveries = []
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
            deliveries = recipient_service.create_data_pipe_alerts(
                data_pipe_event(alert_node)
            )
            asyncio.run(deliver(deliveries))

            message = None
            for line in lines:
                if not line.startswith("data: "):
                    continue
                message = json.loads(line.removeprefix("data: "))
                break
        assert message is not None
        assert message["uuid"] == str(deliveries[0].notification.uuid)
        assert message["type"] == NotificationType.DATA_PIPE_ALERT.value
        assert message["data"]["topic_name"] == alert_node.topic_name
    finally:
        drop_notifications(
            database, [item.notification for item in deliveries]
        )


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
    assert all(
        item.target_user_uuid == regular_user.uuid for item in notifications
    )

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
    _count, notifications = service.list(
        NotificationFilter.unlimited(
            target_user_uuid=crud_notification.target_user_uuid
        )
    )
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
    crud_notification, recipient_service, alert_node, database
) -> None:
    deliveries = recipient_service.create_data_pipe_alerts(
        data_pipe_event(alert_node, value="20")
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
        drop_notifications(
            database, [item.notification for item in deliveries]
        )


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
        service.current_user_uuid()


def test_dispatch_scheduled_instance_state(
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
            deliveries = service.dispatch_scheduled()
            created.extend(item.notification for item in deliveries)
            assert all(
                item.user_uuid == admin_user.uuid for item in deliveries
            )

            instance_alerts = [
                item
                for item in created
                if item.type == NotificationType.INSTANCE_DAILY_STATE.value
            ]
            assert len(instance_alerts) == 1
            assert all(item.push_sse is False for item in deliveries)
            assert "user_count" in instance_alerts[0].data["entities"]
            errors = instance_alerts[0].data["errors"]
            assert isinstance(errors, list)
            assert len(errors) <= 3
            assert all(
                "count" in item and "message" in item for item in errors
            )

            # the same day is dispatched once
            assert service.dispatch_scheduled() == []
            _, notifications = service.list(
                NotificationFilter.unlimited(
                    type=[NotificationType.INSTANCE_DAILY_STATE.value]
                )
            )
            assert len(notifications) == 1
        finally:
            drop_notifications(database, created)


def test_dispatch_scheduled_unit_summary(
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

            deliveries = service.dispatch_scheduled()
            created.extend(item.notification for item in deliveries)

            assert all(item.push_sse is False for item in deliveries)
            assert all(
                item.type != NotificationType.INSTANCE_DAILY_STATE.value
                for item in created
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

            # the same day is dispatched once
            assert service.dispatch_scheduled() == []
        finally:
            drop_notifications(database, created)


def _scheduled_now() -> str:
    """HH:MM of now, waits out the end of a minute so dispatch sees the same one"""
    now = datetime.now(UTC)
    if now.second > 50:
        time.sleep(60 - now.second)
        now = datetime.now(UTC)
    return now.strftime("%H:%M")
