from fastapi import Depends
from sqlmodel import Session

from app.configs.db import get_session
from app.domain.instance_settings_model import InstanceSettings
from app.repositories.base_repository import BaseRepository


class InstanceSettingsRepository(BaseRepository):
    def __init__(self, db: Session = Depends(get_session)) -> None:
        super().__init__(InstanceSettings, db)
