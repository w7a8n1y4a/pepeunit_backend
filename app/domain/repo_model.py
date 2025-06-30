import uuid as uuid_pkg
from datetime import datetime

from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import Field, SQLModel

from app.dto.enum import VisibilityLevel


class Repo(SQLModel, table=True):
    """Репозиторий"""

    __tablename__ = 'repos'

    uuid: uuid_pkg.UUID = Field(primary_key=True, nullable=False, index=True, default_factory=uuid_pkg.uuid4)

    visibility_level: str = Field(nullable=False, default=VisibilityLevel.PUBLIC)

    # unique name Repo on Instance
    name: str = Field(nullable=False, unique=True)
    # datetime Create Repo
    create_datetime: datetime = Field(nullable=False)

    # link to remote repository
    repo_url: str = Field(nullable=False)
    # type of remote hosting
    platform: str = Field(nullable=False)

    # this remote repository is Public ?
    is_public_repository: bool = Field(nullable=False, default=True)
    # if is_public_repository=False - cipher creds to load remote repository
    cipher_credentials_private_repository: str = Field(nullable=True)

    # default branch - need for auto and hand updates
    default_branch: str = Field(nullable=True)

    # repo is compilable ?
    # if is_compilable_repo == True - user will see only tags for updates, app archive: only env and schema
    # if is_compilable_repo == False - user will see all commits for updates, app archive: full repo inside archives
    is_compilable_repo: bool = Field(nullable=False, default=False)
    # assets links by tags
    releases_data: str = Field(nullable=True, default=None)

    # this repository is auto updated?
    is_auto_update_repo: bool = Field(nullable=False, default=True)

    # if is_auto_update_repo = False:
    # commit by default for hand updated Unit, Unit cannot be tapped until the default commit is set
    default_commit: str = Field(nullable=True)

    # if is_auto_update_repo = True:
    # if is_only_tag_update = True - target version is last Tag,
    # if is_only_tag_update = False - last commit in default_branch
    is_only_tag_update: bool = Field(nullable=False, default=False)

    last_update_datetime: datetime = Field(nullable=False)

    # to User link
    creator_uuid: uuid_pkg.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), ForeignKey('users.uuid', ondelete='CASCADE'))
    )

    # to RepositoryRegistry link
    repository_registry_uuid: uuid_pkg.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), ForeignKey('repository_registry.uuid', ondelete='CASCADE'), nullable=False)
    )
