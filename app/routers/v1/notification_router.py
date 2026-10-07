import uuid as uuid_pkg

from fastapi import APIRouter, Depends
from starlette.requests import Request
from starlette.responses import StreamingResponse

from app.configs.db import get_hand_session
from app.configs.errors import NoAccessError
from app.configs.rest import get_notification_service
from app.dto.enum import AgentType
from app.schemas.pydantic.notification import (
    NotificationFilter,
    NotificationRead,
    NotificationSettingsRead,
    NotificationSettingsUpdate,
    NotificationsResult,
    notification_read,
)
from app.services.notification_delivery import notification_delivery
from app.services.notification_service import NotificationService
from app.services.utils import token_depends

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


@router.get("/stream")
async def notifications_stream(
    request: Request,
    jwt_token: str | None = Depends(token_depends),
):
    NotificationService.is_notification_enable()
    # Auth uses a short session. The stream itself must not hold a database
    # connection for as long as the client stays connected.
    if not jwt_token:
        msg = "Notification access not allowed"
        raise NoAccessError(msg)
    with get_hand_session() as db:
        service = get_notification_service(db, None, jwt_token)
        service.access_service.authorization.check_access([AgentType.USER])
        user_uuid = str(service.access_service.current_agent.uuid)
    return StreamingResponse(
        notification_delivery.events(request, user_uuid),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


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
            notification_read(notification) for notification in notifications
        ],
    )


@router.get("/{uuid}", response_model=NotificationRead)
def get_notification(
    uuid: uuid_pkg.UUID,
    notification_service: NotificationService = Depends(
        get_notification_service
    ),
):
    return notification_read(notification_service.get(uuid))


@router.patch("/{uuid}/read", response_model=NotificationRead)
def mark_read(
    uuid: uuid_pkg.UUID,
    notification_service: NotificationService = Depends(
        get_notification_service
    ),
):
    return notification_read(notification_service.mark_read(uuid))
