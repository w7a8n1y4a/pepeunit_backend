import uuid as uuid_pkg
from datetime import datetime

from sqlalchemy import ForeignKey, Column
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import SQLModel, Field

from app.core.enum import VisibilityLevel


class Unit(SQLModel, table=True):
    """Представление физического устройства"""

    __tablename__ = 'units'

    uuid: uuid_pkg.UUID = Field(primary_key=True, nullable=False, index=True, default_factory=uuid_pkg.uuid4)

    # уровень видимости для пользователей
    visibility_level: str = Field(nullable=False, default=VisibilityLevel.PUBLIC.value)

    # уникальное название Unit на узле
    name: str = Field(nullable=False)
    # время создания Unit
    create_datetime: datetime = Field(nullable=False, default_factory=datetime.utcnow)

    # автоматически обновляться при обновлении родительского Repo?
    is_auto_update_from_repo_unit: bool = Field(nullable=False, default=True)

    # если выключено автоматическое обновление:
    # название ветки
    repo_branch: str = Field(nullable=True)
    # название коммита, если выбран тег, присвоится коммит, которому присвоен тег
    repo_commit: str = Field(nullable=True)

    # последнее состояние Unit
    unit_state_dict: str = Field(nullable=True)
    # зашифрованный env устройства
    cipher_env_dict: str = Field(nullable=True)

    # создатель
    creator_uuid: uuid_pkg.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), ForeignKey('users.uuid', ondelete='CASCADE'))
    )
    # родительский репозиторий
    repo_uuid: uuid_pkg.UUID = Field(sa_column=Column(UUID(as_uuid=True), ForeignKey('repos.uuid', ondelete='CASCADE')))
