import uuid as uuid_pkg
from datetime import datetime

from sqlalchemy import ForeignKey, Column
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import SQLModel, Field

from app.repositories.enum import VisibilityLevel


class Repo(SQLModel, table=True):
    """Репозиторий"""

    __tablename__ = 'repos'

    uuid: uuid_pkg.UUID = Field(primary_key=True, nullable=False, index=True, default_factory=uuid_pkg.uuid4)

    visibility_level: str = Field(nullable=False, default=VisibilityLevel.PUBLIC)

    # unique name Repo on Instance
    name: str = Field(nullable=False, unique=True)
    # datetime Create Repo
    create_datetime: datetime = Field(nullable=False, default_factory=datetime.utcnow)

    # link to remote repository Gitlab or Github
    repo_url: str = Field(nullable=False)
    # this remote repository is Public ?
    is_public_repository: bool = Field(nullable=False, default=True)
    # if is_public_repository=False - cipher creds to load remote repository
    cipher_credentials_private_repository: str = Field(nullable=True)

    # default branch - need for auto and hand updates
    default_branch: str = Field(nullable=True)

    # this repository is auto updated?
    is_auto_update_repo: bool = Field(nullable=False, default=True)

    # if is_auto_update_repo = False:
    # commit by default for hand updated Unit, Unit cannot be tapped until the default commit is set
    default_commit: str = Field(nullable=True)

    # if is_auto_update_repo = True:
    # if is_only_tag_update = True - target version is last Tag,
    # if is_only_tag_update = False - last commit in default_branch
    is_only_tag_update: bool = Field(nullable=False, default=False)
    # update rate in seconds - minimal 600 s
    update_frequency_in_seconds: int = Field(nullable=False, default=86400)

    last_update_datetime: datetime = Field(nullable=False, default_factory=datetime.utcnow)

    # to User link
    creator_uuid: uuid_pkg.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), ForeignKey('users.uuid', ondelete='CASCADE'))
    )
