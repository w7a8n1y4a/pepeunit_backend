from datetime import UTC, datetime

from fastapi import Depends
from sqlmodel import Session, SQLModel

from app.configs.db import get_session
from app.domain.icon_model import Icon
from app.repositories.base_repository import BaseRepository
from app.services.icon_image import IconImage
from app.services.validators import is_valid_object


class IconRepository(BaseRepository):
    def __init__(self, db: Session = Depends(get_session)) -> None:
        super().__init__(Icon, db)

    def stage(self, image: bytes) -> Icon:
        icon = Icon(
            image_bin=image,
            create_datetime=datetime.now(UTC),
            size=len(image),
            image_hash=IconImage.md5(image),
        )
        self.db.add(icon)
        self.db.flush()
        return icon

    def replace(self, entity: SQLModel, image: bytes) -> Icon:
        target_entity = self.db.get(
            type(entity), entity.uuid, with_for_update=True
        )
        is_valid_object(target_entity)

        icon = self.stage(image)

        old_uuid = target_entity.icon_uuid
        target_entity.icon_uuid = icon.uuid
        self.db.flush()
        self.db.delete(self.get(Icon(uuid=old_uuid)))
        self.db.commit()
        self.db.refresh(icon)
        return icon
