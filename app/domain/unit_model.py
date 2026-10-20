import json
import uuid as uuid_pkg
from datetime import datetime

from sqlalchemy import Column, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import Field, SQLModel

from app.domain.icon_model import Icon
from app.dto.enum import VisibilityLevel


class Unit(SQLModel, table=True):
    """
    Representation of a physical device
    """

    __tablename__ = "units"
    __table_args__ = (
        UniqueConstraint(
            "creator_uuid",
            "name",
            name="units_creator_name_key",
        ),
    )

    uuid: uuid_pkg.UUID = Field(
        primary_key=True,
        nullable=False,
        index=True,
        default_factory=uuid_pkg.uuid4,
    )

    # Default picture is generated from the unit uuid.
    icon_uuid: uuid_pkg.UUID = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey(
                Icon.__table__.c.uuid,
                name="units_icon_uuid_fkey",
                ondelete="RESTRICT",
            ),
            nullable=False,
            index=True,
        )
    )

    visibility_level: str = Field(
        nullable=False, default=VisibilityLevel.PUBLIC
    )

    # Unique for the creator
    name: str = Field(nullable=False)
    create_datetime: datetime = Field(nullable=False)

    # Follow target_branch. Last tag when is_only_tag_update or
    # is_compilable_unit, otherwise the branch head.
    is_auto_update_unit: bool = Field(nullable=False, default=True)

    # Compiled firmware uses tags only. The archive contains env and schema.
    is_compilable_unit: bool = Field(nullable=False, default=False)

    # With is_auto_update_unit, follow the last tag instead of the branch head.
    is_only_tag_update: bool = Field(nullable=False, default=True)

    # Release asset name when is_compilable_unit is true.
    target_firmware_platform: str = Field(nullable=True, default=None)

    target_branch: str = Field(nullable=False)
    # Pin used when is_auto_update_unit is false.
    target_commit: str = Field(nullable=True)

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
        sa_column=Column(
            UUID(as_uuid=True), ForeignKey("users.uuid", ondelete="CASCADE")
        )
    )
    repository_registry_uuid: uuid_pkg.UUID = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey("repository_registry.uuid", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )

    @property
    def unit_state(self) -> dict | None:
        if self.unit_state_dict:
            try:
                return json.loads(self.unit_state_dict)
            except json.JSONDecodeError, TypeError, ValueError:
                pass
        return None

    def to_dict(self, include_unit_state: bool = True) -> dict:
        base_dict = self.dict()
        if include_unit_state:
            base_dict["unit_state"] = self.unit_state
        return base_dict
