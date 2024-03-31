import uuid as uuid_pkg
from datetime import datetime

from sqlmodel import SQLModel, Field


class Test(SQLModel, table=True):
    """TODO Подлежит удалению"""

    __tablename__ = 'tests'

    uuid: uuid_pkg.UUID = Field(primary_key=True, nullable=False, index=True, default_factory=uuid_pkg.uuid4)

    # роль на узле
    value: str = Field(nullable=True, default=None)

    # время создания User
    create_datetime: datetime = Field(nullable=False, default_factory=datetime.utcnow)
