import uuid as uuid_pkg
from datetime import datetime

from fastapi import UploadFile
from pydantic import BaseModel

from app.dto.enum import IconEntityType


class IconUpload(BaseModel):
    entity_uuid: uuid_pkg.UUID
    entity_type: IconEntityType
    file: UploadFile


class IconRead(BaseModel):
    uuid: uuid_pkg.UUID
    size: int
    image_hash: str
    create_datetime: datetime
