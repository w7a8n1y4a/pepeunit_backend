import uuid as uuid_pkg

import pytest

from app.domain.notification_model import Notification
from app.dto.enum import UserStatus
from app.repositories.user_repository import UserRepository
from app.schemas.pydantic.notification import (
    NotificationFilter,
    NotificationSettingsUpdate,
)
from tests.integration.helpers.notifications import drop_notification
from tests.integration.helpers.services import notification_service


def _verify(database, user):
    user.status = UserStatus.VERIFIED
    return UserRepository(db=database).update(user.uuid, user)


@pytest.fixture
def crud_notification(extra_user, extra_user_token, database, cc) -> Notification:
    _verify(database, extra_user)
    service = notification_service(database, cc, extra_user_token)
    service.update_settings(
        NotificationSettingsUpdate(is_data_pipe_alert_enable=True)
    )
    service.create_data_pipe_alerts(
        {
            "unit_node_uuid": str(uuid_pkg.uuid4()),
            "unit_uuid": str(uuid_pkg.uuid4()),
            "value": "12.5",
            "event": "Fired",
            "condition": "Above",
            "severity": "Warning",
            "threshold_value": "10",
        }
    )
    _, notifications = service.list(NotificationFilter.unlimited())
    notification = notifications[0]
    yield notification
    drop_notification(database, notification.uuid)
