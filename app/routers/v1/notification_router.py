import uuid as uuid_pkg
from typing import Annotated

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect

from app.configs.db import get_hand_session
from app.configs.errors import NoAccessError
from app.configs.rest import get_notification_service
from app.schemas.pydantic.notification import (
    NotificationFilter,
    NotificationRead,
    NotificationSettingsRead,
    NotificationSettingsUpdate,
    NotificationsResult,
    UnitLogAggregateRead,
    UnitLogAggregatesResult,
)
from app.services.notification_delivery import notification_socket_hub
from app.services.notification_service import NotificationService

router = APIRouter()


@router.get("/settings", response_model=NotificationSettingsRead)
def get_settings(
    notification_service: NotificationService = Depends(
        get_notification_service
    ),
):
    return NotificationSettingsRead(
        **notification_service.get_settings().dict()
    )


@router.patch("/settings", response_model=NotificationSettingsRead)
def update_settings(
    data: NotificationSettingsUpdate,
    notification_service: NotificationService = Depends(
        get_notification_service
    ),
):
    return NotificationSettingsRead(
        **notification_service.update_settings(data).dict()
    )


@router.patch("/read", response_model=int)
def mark_all_read(
    notification_service: NotificationService = Depends(
        get_notification_service
    ),
):
    return notification_service.mark_all_read()


@router.websocket("/ws")
async def notifications_ws(
    websocket: WebSocket,
    x_auth_token: Annotated[str | None, Query(alias="x-auth-token")] = None,
):
    await websocket.accept()
    user_uuid = _user_uuid_from_token(x_auth_token)
    if user_uuid is None:
        await websocket.close(code=1008)
        return

    await notification_socket_hub.connect(user_uuid, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await notification_socket_hub.disconnect(user_uuid, websocket)


@router.get("", response_model=NotificationsResult)
def get_notifications(
    filters: NotificationFilter = Depends(NotificationFilter),
    notification_service: NotificationService = Depends(
        get_notification_service
    ),
):
    count, notifications = notification_service.list(filters)
    return NotificationsResult(
        count=count,
        notifications=[
            NotificationRead(**notification.dict())
            for notification in notifications
        ],
    )


@router.get("/{uuid}", response_model=NotificationRead)
def get_notification(
    uuid: uuid_pkg.UUID,
    notification_service: NotificationService = Depends(
        get_notification_service
    ),
):
    return NotificationRead(**notification_service.get(uuid).dict())


@router.get("/{uuid}/logs", response_model=UnitLogAggregatesResult)
def get_notification_unit_logs(
    uuid: uuid_pkg.UUID,
    notification_service: NotificationService = Depends(
        get_notification_service
    ),
):
    logs = notification_service.get_unit_log_aggregation(uuid)
    items = [UnitLogAggregateRead(**item) for item in logs]
    return UnitLogAggregatesResult(count=len(items), logs=items)


@router.patch("/{uuid}/read", response_model=NotificationRead)
def mark_read(
    uuid: uuid_pkg.UUID,
    notification_service: NotificationService = Depends(
        get_notification_service
    ),
):
    return NotificationRead(**notification_service.mark_read(uuid).dict())


def _user_uuid_from_token(token: str | None) -> str | None:
    """Browsers cannot set headers on a socket, so the token is a query param"""
    if not token:
        return None
    try:
        with get_hand_session() as db:
            service = get_notification_service(db, None, token)
            return str(service.socket_user_uuid())
    except NoAccessError:
        return None
