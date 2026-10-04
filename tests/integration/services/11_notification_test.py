import logging
import uuid as uuid_pkg
from datetime import UTC, datetime, timedelta

import pytest

from app import settings
from app.configs.errors import NoAccessError, NotificationError
from app.domain.notification_settings_model import (
    DEFAULT_SCHEDULED_NOTIFICATION_TIME,
)
from app.dto.clickhouse.log import UnitLog
from app.dto.enum import LogLevel, NotificationType, UserStatus
from app.repositories.unit_log_repository import UnitLogRepository
from app.repositories.user_repository import UserRepository
from app.schemas.pydantic.notification import (
    NotificationFilter,
    NotificationSettingsUpdate,
)
from tests.integration.helpers.notifications import drop_notification
from tests.integration.helpers.services import notification_service


def test_get_notification_settings(
    regular_user, regular_user_token, database, cc
) -> None:
    settings_row = notification_service(
        database, cc, regular_user_token
    ).get_settings()
    logging.info(settings_row.uuid)
    assert settings_row.user_uuid == regular_user.uuid
    assert settings_row.is_scheduled_alert_enable is False
    assert settings_row.is_data_pipe_alert_enable is False
    assert settings_row.is_telegram_alert_enable is False
    assert settings_row.scheduled_notification_time == "16:00"
    assert (
        settings_row.scheduled_notification_time
        == DEFAULT_SCHEDULED_NOTIFICATION_TIME
    )


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


def test_create_data_pipe_alert(crud_notification, extra_user) -> None:
    logging.info(crud_notification.uuid)
    assert crud_notification.type == NotificationType.DATA_PIPE_ALERT.value
    assert crud_notification.target_user_uuid == extra_user.uuid
    assert crud_notification.is_read is False
    assert crud_notification.read_datetime is None
    assert crud_notification.data["value"] == "12.5"
    assert crud_notification.data["threshold_max"] == 10
    assert crud_notification.data["unit_name"] is None
    assert crud_notification.data["condition"] == "Above"
    assert crud_notification.data["threshold_min"] is None
    assert crud_notification.data["match_values"] is None


def _enable_data_pipe_alerts(extra_user, extra_user_token, database, cc):
    extra_user.status = UserStatus.VERIFIED
    UserRepository(db=database).update(extra_user.uuid, extra_user)
    service = notification_service(database, cc, extra_user_token)
    service.update_settings(
        NotificationSettingsUpdate(is_data_pipe_alert_enable=True)
    )
    return service


def _data_pipe_event(**fields) -> dict:
    return {
        "unit_node_uuid": str(uuid_pkg.uuid4()),
        "unit_uuid": str(uuid_pkg.uuid4()),
        "value": "12.5",
        **fields,
    }


def test_create_data_pipe_alert_above_condition(
    extra_user, extra_user_token, database, cc
) -> None:
    service = _enable_data_pipe_alerts(extra_user, extra_user_token, database, cc)
    service.create_data_pipe_alerts(
        _data_pipe_event(condition="Above", threshold_max="10")
    )

    _, notifications = service.list(NotificationFilter.unlimited())
    try:
        assert len(notifications) == 1
        data = notifications[0].data
        assert data["condition"] == "Above"
        assert data["threshold_max"] == 10
        assert data["threshold_min"] is None
    finally:
        for item in notifications:
            drop_notification(database, item.uuid)


def test_create_data_pipe_alert_range_condition(
    extra_user, extra_user_token, database, cc
) -> None:
    service = _enable_data_pipe_alerts(extra_user, extra_user_token, database, cc)
    service.create_data_pipe_alerts(
        _data_pipe_event(
            condition="OutOfRange",
            threshold_min="1.5",
            threshold_max="10",
        )
    )

    _, notifications = service.list(NotificationFilter.unlimited())
    try:
        assert len(notifications) == 1
        data = notifications[0].data
        assert data["condition"] == "OutOfRange"
        assert data["threshold_min"] == 1.5
        assert data["threshold_max"] == 10
    finally:
        for item in notifications:
            drop_notification(database, item.uuid)


def test_create_data_pipe_alert_text_condition(
    extra_user, extra_user_token, database, cc
) -> None:
    service = _enable_data_pipe_alerts(extra_user, extra_user_token, database, cc)
    service.create_data_pipe_alerts(
        _data_pipe_event(
            value="sensor overheat",
            condition="Contains",
            match_values='["overheat", "fire"]',
        )
    )

    _, notifications = service.list(NotificationFilter.unlimited())
    try:
        assert len(notifications) == 1
        data = notifications[0].data
        assert data["condition"] == "Contains"
        assert data["match_values"] == ["overheat", "fire"]
        assert data["threshold_min"] is None
        assert data["threshold_max"] is None
    finally:
        for item in notifications:
            drop_notification(database, item.uuid)


def test_data_pipe_alert_invalid_rule(
    extra_user, extra_user_token, database, cc
) -> None:
    service = _enable_data_pipe_alerts(extra_user, extra_user_token, database, cc)

    invalid_rules = [
        {},
        {"condition": "Above"},
        {"condition": "Above", "threshold_max": "high"},
        {"condition": "Above", "threshold_max": "nan"},
        {"condition": "Above", "threshold_min": "1"},
        {"condition": "Below"},
        {"condition": "Below", "threshold_max": "1"},
        {"condition": "OutOfRange", "threshold_min": "1"},
        {"condition": "InRange", "threshold_max": "1"},
        {"condition": "Equals"},
        {"condition": "Contains", "match_values": "[]"},
        {"condition": "Contains", "match_values": "not json"},
        {"condition": "Contains", "match_values": '"overheat"'},
        {"condition": "Sideways", "threshold_max": "10"},
        {"threshold_max": "10"},
    ]
    for fields in invalid_rules:
        service.create_data_pipe_alerts(_data_pipe_event(**fields))

    count, _notifications = service.list(NotificationFilter.unlimited())
    assert count == 0


def test_data_pipe_alert_disabled(extra_user, extra_user_token, database, cc) -> None:
    extra_user.status = UserStatus.VERIFIED
    UserRepository(db=database).update(extra_user.uuid, extra_user)
    service = notification_service(database, cc, extra_user_token)
    service.create_data_pipe_alerts(
        {
            "unit_node_uuid": str(uuid_pkg.uuid4()),
            "unit_uuid": str(uuid_pkg.uuid4()),
            "value": "12.5",
            "condition": "Above",
            "threshold_max": "10",
        }
    )
    count, notifications = service.list(NotificationFilter.unlimited())
    assert count == 0
    assert notifications == []


def test_data_pipe_alert_incomplete_payload(
    extra_user, extra_user_token, database, cc
) -> None:
    extra_user.status = UserStatus.VERIFIED
    UserRepository(db=database).update(extra_user.uuid, extra_user)
    service = notification_service(database, cc, extra_user_token)
    service.update_settings(
        NotificationSettingsUpdate(is_data_pipe_alert_enable=True)
    )
    service.create_data_pipe_alerts({"value": "12.5"})
    count, _notifications = service.list(NotificationFilter.unlimited())
    assert count == 0


def test_get_notification(
    crud_notification, extra_user_token, database, cc
) -> None:
    service = notification_service(database, cc, extra_user_token)
    assert service.get(crud_notification.uuid).uuid == crud_notification.uuid


def test_get_notification_not_target(
    crud_notification, regular_user_token, database, cc
) -> None:
    service = notification_service(database, cc, regular_user_token)
    with pytest.raises(NoAccessError):
        service.get(crud_notification.uuid)


def test_get_many_notification(
    crud_notification, extra_user, extra_user_token, database, cc
) -> None:
    service = notification_service(database, cc, extra_user_token)
    count, notifications = service.list(NotificationFilter.unlimited())
    assert count >= 1
    assert any(item.uuid == crud_notification.uuid for item in notifications)
    assert all(item.target_user_uuid == extra_user.uuid for item in notifications)

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


def test_list_notifications_only_own(
    crud_notification, regular_user_token, database, cc
) -> None:
    service = notification_service(database, cc, regular_user_token)
    _count, notifications = service.list(NotificationFilter.unlimited())
    assert all(item.uuid != crud_notification.uuid for item in notifications)


def test_mark_notification_read(
    crud_notification, extra_user_token, database, cc
) -> None:
    service = notification_service(database, cc, extra_user_token)
    read = service.mark_read(crud_notification.uuid)
    assert read.is_read is True
    assert read.read_datetime is not None

    again = service.mark_read(crud_notification.uuid)
    assert again.read_datetime == read.read_datetime


def test_mark_all_notifications_read(
    crud_notification, extra_user_token, database, cc
) -> None:
    service = notification_service(database, cc, extra_user_token)
    service.create_data_pipe_alerts(
        {
            "unit_node_uuid": str(uuid_pkg.uuid4()),
            "unit_uuid": str(uuid_pkg.uuid4()),
            "value": "20",
            "condition": "Above",
            "threshold_max": "10",
        }
    )
    marked = service.mark_all_read()
    assert marked >= 2
    _count, notifications = service.list(NotificationFilter.unlimited())
    assert all(item.is_read is True for item in notifications)
    assert service.mark_all_read() == 0


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


def test_unit_log_aggregation_wrong_type(
    crud_notification, extra_user_token, database, cc
) -> None:
    service = notification_service(database, cc, extra_user_token)
    with pytest.raises(NotificationError):
        service.get_unit_log_aggregation(crud_notification.uuid)


def test_dispatch_scheduled_instance_state(
    admin_user, admin_user_token, database, cc
) -> None:
    repository = UserRepository(db=database)
    previous_status = admin_user.status
    admin_user.status = UserStatus.VERIFIED
    repository.update(admin_user.uuid, admin_user)

    service = notification_service(database, cc, admin_user_token)
    saved = service.get_settings()
    saved_scheduled = saved.is_scheduled_alert_enable
    saved_time = saved.scheduled_notification_time
    saved_pipe = saved.is_data_pipe_alert_enable
    saved_telegram = saved.is_telegram_alert_enable
    created = []
    try:
        service.update_settings(
            NotificationSettingsUpdate(
                is_scheduled_alert_enable=True,
                scheduled_notification_time=datetime.now(UTC).strftime("%H:%M"),
            )
        )
        before = {item.uuid for item in service.list(NotificationFilter.unlimited())[1]}
        service.dispatch_scheduled()
        _, notifications = service.list(NotificationFilter.unlimited())
        created.extend(item for item in notifications if item.uuid not in before)

        instance_alerts = [
            item
            for item in created
            if item.type == NotificationType.INSTANCE_DAILY_STATE.value
        ]
        assert len(instance_alerts) == 1
        assert "user_count" in instance_alerts[0].data["entities"]
        assert isinstance(instance_alerts[0].data["errors"], list)

        service.dispatch_scheduled()
        _, notifications = service.list(
            NotificationFilter.unlimited(
                type=[NotificationType.INSTANCE_DAILY_STATE.value]
            )
        )
        assert len(notifications) == 1
    finally:
        admin_user.status = previous_status
        repository.update(admin_user.uuid, admin_user)
        service.update_settings(
            NotificationSettingsUpdate(
                is_scheduled_alert_enable=saved_scheduled,
                scheduled_notification_time=saved_time,
                is_data_pipe_alert_enable=saved_pipe,
                is_telegram_alert_enable=saved_telegram,
            )
        )
        for item in created:
            drop_notification(database, item.uuid)


def test_dispatch_scheduled_unit_summary(
    live_units, regular_user, regular_user_token, database, cc
) -> None:
    repository = UserRepository(db=database)
    previous_status = regular_user.status
    regular_user.status = UserStatus.VERIFIED
    repository.update(regular_user.uuid, regular_user)

    service = notification_service(database, cc, regular_user_token)
    saved = service.get_settings()
    saved_scheduled = saved.is_scheduled_alert_enable
    saved_time = saved.scheduled_notification_time
    saved_pipe = saved.is_data_pipe_alert_enable
    saved_telegram = saved.is_telegram_alert_enable
    created = []
    unit = live_units.universal_manual_unit
    try:
        service.update_settings(
            NotificationSettingsUpdate(
                is_scheduled_alert_enable=True,
                scheduled_notification_time=datetime.now(UTC).strftime("%H:%M"),
            )
        )
        before = {item.uuid for item in service.list(NotificationFilter.unlimited())[1]}
        service.dispatch_scheduled()
        _, notifications = service.list(NotificationFilter.unlimited())
        created.extend(item for item in notifications if item.uuid not in before)

        assert all(
            item.type != NotificationType.INSTANCE_DAILY_STATE.value
            for item in created
        )
        summary = next(
            item
            for item in created
            if item.type == NotificationType.UNIT_DAILY_SUMMARY.value
            and item.data["unit_uuid"] == str(unit.uuid)
        )
        assert summary.data["unit_name"] == unit.name

        error_text = f"integration alert {uuid_pkg.uuid4()}"
        critical_text = f"integration critical {uuid_pkg.uuid4()}"
        info_text = f"integration info {uuid_pkg.uuid4()}"
        log_time = _inside_period(summary.data["period_start"])
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

        logs = service.get_unit_log_aggregation(summary.uuid)
        errors = [item for item in logs if item["text"] == error_text]
        critical = [item for item in logs if item["text"] == critical_text]
        assert len(errors) == 1
        assert errors[0]["count"] == 2
        assert errors[0]["level"] == LogLevel.ERROR.value
        assert len(critical) == 1
        assert critical[0]["count"] == 1
        assert critical[0]["level"] == LogLevel.CRITICAL.value
        assert all(item["text"] != info_text for item in logs)

        _, before_repeat = service.list(
            NotificationFilter.unlimited(
                type=[NotificationType.UNIT_DAILY_SUMMARY.value]
            )
        )
        service.dispatch_scheduled()
        _, after_repeat = service.list(
            NotificationFilter.unlimited(
                type=[NotificationType.UNIT_DAILY_SUMMARY.value]
            )
        )
        assert len(after_repeat) == len(before_repeat)
    finally:
        regular_user.status = previous_status
        repository.update(regular_user.uuid, regular_user)
        service.update_settings(
            NotificationSettingsUpdate(
                is_scheduled_alert_enable=saved_scheduled,
                scheduled_notification_time=saved_time,
                is_data_pipe_alert_enable=saved_pipe,
                is_telegram_alert_enable=saved_telegram,
            )
        )
        for item in created:
            drop_notification(database, item.uuid)


def _inside_period(period_start: str) -> datetime:
    start = datetime.fromisoformat(period_start)
    if start.tzinfo is not None:
        start = start.astimezone(UTC).replace(tzinfo=None)
    return start + timedelta(minutes=1)
