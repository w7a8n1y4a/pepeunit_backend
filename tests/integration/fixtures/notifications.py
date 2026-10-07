import pytest

from app.domain.notification_model import Notification
from app.domain.unit_node_model import UnitNode
from app.dto.enum import UnitNodeTypeEnum
from app.schemas.pydantic.notification import NotificationSettingsUpdate
from app.schemas.pydantic.unit_node import UnitNodeFilter
from app.services.notification_service import NotificationService
from tests.integration.helpers.notifications import (
    as_recipient,
    data_pipe_notification,
    deliver_notification,
    drop_notification,
)
from tests.integration.helpers.services import unit_node_service


@pytest.fixture(scope="session")
def alert_node(live_units, regular_user_token, database, cc) -> UnitNode:
    """Output node created by the regular user"""
    _, nodes = unit_node_service(database, cc, regular_user_token).list(
        UnitNodeFilter.unlimited(
            unit_uuid=live_units.universal_manual_unit.uuid,
            type=[UnitNodeTypeEnum.OUTPUT],
        )
    )
    return nodes[0]


@pytest.fixture
def recipient_service(
    regular_user, regular_user_token, database, cc
) -> NotificationService:
    """Regular user receives data pipe alerts, settings restored afterwards"""
    with as_recipient(
        database, cc, regular_user, regular_user_token
    ) as service:
        service.update_settings(
            NotificationSettingsUpdate(is_data_pipe_alert_enable=True)
        )
        yield service


@pytest.fixture
def crud_notification(
    recipient_service, alert_node, regular_user, live_units, database
) -> Notification:
    notification = deliver_notification(
        recipient_service,
        data_pipe_notification(
            alert_node,
            regular_user,
            live_units.universal_manual_unit.name,
        ),
    )
    yield notification
    drop_notification(database, notification.uuid)
