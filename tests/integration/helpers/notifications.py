from app.domain.notification_model import Notification
from app.repositories.notification_repository import NotificationRepository


def drop_notification(database, uuid) -> None:
    try:
        NotificationRepository(database).delete(Notification(uuid=uuid))
    except Exception:
        pass
