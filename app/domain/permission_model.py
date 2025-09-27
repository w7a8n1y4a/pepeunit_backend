import uuid as uuid_pkg

from pydantic import BaseModel
from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import Field, SQLModel

from app.dto.enum import PermissionEntities


class Permission(SQLModel, table=True):
    """Доступы"""

    __tablename__ = "permissions"

    uuid: uuid_pkg.UUID = Field(
        primary_key=True,
        nullable=False,
        index=True,
        default_factory=uuid_pkg.uuid4,
    )

    # User, Unit, Unit Node
    agent_type: str = Field(nullable=False)
    agent_user_uuid: uuid_pkg.UUID = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey("users.uuid", ondelete="CASCADE"),
            nullable=True,
        )
    )
    agent_unit_uuid: uuid_pkg.UUID = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey("units.uuid", ondelete="CASCADE"),
            nullable=True,
        )
    )

    # Repo, Unit, UnitNode
    resource_type: str = Field(nullable=False)
    resource_repo_uuid: uuid_pkg.UUID = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey("repos.uuid", ondelete="CASCADE"),
            nullable=True,
        )
    )
    resource_unit_uuid: uuid_pkg.UUID = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey("units.uuid", ondelete="CASCADE"),
            nullable=True,
        )
    )
    resource_unit_node_uuid: uuid_pkg.UUID = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey("units_nodes.uuid", ondelete="CASCADE"),
            nullable=True,
        )
    )


class PermissionBaseType(BaseModel):
    uuid: uuid_pkg.UUID | None = None

    agent_uuid: uuid_pkg.UUID | None = None
    agent_type: PermissionEntities | None = None

    resource_uuid: uuid_pkg.UUID | None = None
    resource_type: PermissionEntities | None = None
