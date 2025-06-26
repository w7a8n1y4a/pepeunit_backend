import uuid as uuid_pkg
from datetime import datetime

from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import Field, SQLModel

from app.dto.enum import VisibilityLevel


class RepositoryRegistry(SQLModel, table=True):
    """Реестр Репозиториев"""

    __tablename__ = 'repository_registry'

    uuid: uuid_pkg.UUID = Field(primary_key=True, nullable=False, index=True, default_factory=uuid_pkg.uuid4)

    # type of remote hosting
    platform: str = Field(nullable=False)
    # link to remote repository
    repository_url: str = Field(nullable=False, unique=True)
    # this remote repository is Public ?
    is_public_repository: bool = Field(nullable=False, default=True)
    # size on disk in bytes, for git repository
    local_repository_size: int = Field(nullable=False, default=0)

    # last sync status
    sync_status: str = Field(nullable=True)
    # error last sync
    sync_error: str = Field(nullable=True)
    # time last sync
    sync_last_datetime: datetime = Field(nullable=True)

    create_datetime: datetime = Field(nullable=False)
    last_update_datetime: datetime = Field(nullable=False)

    # to User link
    creator_uuid: uuid_pkg.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), ForeignKey('users.uuid', ondelete='CASCADE'))
    )
