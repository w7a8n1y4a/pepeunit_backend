import uuid as uuid_pkg
from datetime import datetime

from sqlalchemy import Column, LargeBinary
from sqlmodel import Field, SQLModel


class Icon(SQLModel, table=True):
    """PNG stored in Postgres. Entities keep only icon_uuid."""

    __tablename__ = "icons"

    uuid: uuid_pkg.UUID = Field(
        primary_key=True,
        nullable=False,
        index=True,
        default_factory=uuid_pkg.uuid4,
    )
    # Raw PNG bytes in Postgres. The original file name is not stored.
    image_bin: bytes = Field(sa_column=Column(LargeBinary, nullable=False))
    create_datetime: datetime = Field(nullable=False)
    # Byte length of image_bin.
    size: int = Field(nullable=False)
    # MD5 of image_bin. Clients use it as a cache key.
    image_hash: str = Field(nullable=False, max_length=32, index=True)
