import uuid as uuid_pkg
from datetime import datetime

from sqlalchemy import ForeignKey, Column
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import SQLModel, Field

from app.core.enum import VisibilityLevel


class Repo(SQLModel, table=True):
    """Репозиторий"""

    __tablename__ = 'repos'

    uuid: uuid_pkg.UUID = Field(primary_key=True, nullable=False, index=True, default_factory=uuid_pkg.uuid4)

    # уровень видимости для пользователей
    visibility_level: str = Field(nullable=False, default=VisibilityLevel.PUBLIC.value)

    # уникальное название Repo на узле
    name: str = Field(nullable=False, unique=True)
    # время создания Repo
    create_datetime: datetime = Field(nullable=False, default_factory=datetime.utcnow)

    # линк до удалённого репозитория
    repo_url: str = Field(nullable=False)
    # репозиторий публичен?
    is_public_repository: bool = Field(nullable=False, default=True)
    # зашифрованные данные доступа до приватного репозитория
    cipher_credentials_private_repository: str = Field(nullable=True)

    # ветка по умолчанию для обновляющихся Unit, Unit нельзя ответвить пока не установлена ветка по умолчанию
    default_branch: str = Field(nullable=True)
    # репозиторий автоматически обновляем?
    is_auto_update_repo: bool = Field(nullable=False, default=True)
    # частота обновлений в секундах, cron делает этот таск 1 раз в 10 минут
    update_frequency_in_seconds: int = Field(nullable=False, default=86400)
    # время последнего обновления, от которого отсчитывается следующий запрос
    last_update_datetime: datetime = Field(nullable=False, default_factory=datetime.utcnow)

    # создатель
    creator_uuid: uuid_pkg.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), ForeignKey('users.uuid', ondelete='CASCADE'))
    )
