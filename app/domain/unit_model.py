import json
import uuid as uuid_pkg
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import Field, SQLModel

from app.repositories.enum import VisibilityLevel


class Unit(SQLModel, table=True):
    """
    Представление физического устройства
    """

    __tablename__ = 'units'

    uuid: uuid_pkg.UUID = Field(primary_key=True, nullable=False, index=True, default_factory=uuid_pkg.uuid4)

    visibility_level: str = Field(nullable=False, default=VisibilityLevel.PUBLIC)

    # Unique Unit name on Instance
    name: str = Field(nullable=False, unique=True)
    create_datetime: datetime = Field(nullable=False)

    # Automatically update when the parent Repo is updated?
    # the last tag or commit in the default Repo branch is taken automatically
    is_auto_update_from_repo_unit: bool = Field(nullable=False, default=True)

    # if is_compilable_repo == True - link names from assets releases
    target_firmware_platform: str = Field(nullable=True, default=None)

    # if is_auto_update_from_repo_unit = False
    # target branch name
    repo_branch: str = Field(nullable=True)
    # target commit name - if target is Tag - will be assigned to the commit corresponding Tag
    repo_commit: str = Field(nullable=True)

    last_update_datetime: datetime = Field(nullable=False)

    # last state Unit
    unit_state_dict: str = Field(nullable=True)
    # this information directly from Unit
    current_commit_version: str = Field(nullable=True)
    # cipher aes256 env Unit - only for creator
    cipher_env_dict: str = Field(nullable=True)
    # cipher aes256 storage for unit state
    cipher_state_storage: str = Field(nullable=True)

    # status update firmware for unit
    firmware_update_status: str = Field(nullable=True)
    # error text when error update
    firmware_update_error: str = Field(nullable=True)
    # datetime last RequestSent to Unit
    last_firmware_update_datetime: datetime = Field(nullable=True)

    # to User link
    creator_uuid: uuid_pkg.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), ForeignKey('users.uuid', ondelete='CASCADE'))
    )
    # to Repo link
    repo_uuid: uuid_pkg.UUID = Field(sa_column=Column(UUID(as_uuid=True), ForeignKey('repos.uuid', ondelete='CASCADE')))

    @property
    def unit_state(self) -> Optional[dict]:
        if self.unit_state_dict:
            try:
                return json.loads(self.unit_state_dict)
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
        return None

    def to_dict(self, include_unit_state: bool = True) -> dict:
        base_dict = self.dict()
        if include_unit_state:
            base_dict["unit_state"] = self.unit_state
        return base_dict
