import uuid as uuid_pkg

from fastapi import APIRouter, Depends
from starlette.requests import Request
from starlette.responses import StreamingResponse

from app.configs.db import get_hand_session
from app.configs.errors import NoAccessError
from app.configs.rest import get_notification_service
from app.schemas.pydantic.notification import (
    NotificationFilter,
    NotificationRead,
    NotificationSettingsRead,
    NotificationSettingsUpdate,
    NotificationsResult,
)
from app.services.notification_delivery import notification_events
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
    # Auth uses a short session. The stream itself must not hold a database
    # connection for as long as the client stays connected.
    user_uuid = _user_uuid_from_token(jwt_token)
    return StreamingResponse(
        notification_events(request, user_uuid),
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


@router.patch("/{uuid}/read", response_model=NotificationRead)
def mark_read(
    uuid: uuid_pkg.UUID,
    notification_service: NotificationService = Depends(
        get_notification_service
    ),
):
    return NotificationRead(**notification_service.mark_read(uuid).dict())


def _user_uuid_from_token(token: str | None) -> str:
    if not token:
        msg = "Notification access not allowed"
        raise NoAccessError(msg)
    with get_hand_session() as db:
        service = get_notification_service(db, None, token)
        return str(service.current_user_uuid())
