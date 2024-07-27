import uuid as pkg_uuid
from typing import Optional

from pydantic import BaseModel
from sqlalchemy import ForeignKey, Column
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import SQLModel, Field

from app.repositories.enum import PermissionEntities


class Permission(SQLModel, table=True):
    """Доступы"""

    __tablename__ = 'permissions'

    uuid: pkg_uuid.UUID = Field(primary_key=True, nullable=False, index=True, default_factory=pkg_uuid.uuid4)

    # User, Unit, Unit Node
    agent_type: str = Field(nullable=False)
    agent_user_uuid: pkg_uuid.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), ForeignKey('users.uuid', ondelete='CASCADE'), nullable=True)
    )
    agent_unit_uuid: pkg_uuid.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), ForeignKey('units.uuid', ondelete='CASCADE'), nullable=True)
    )
    agent_unit_node_uuid: pkg_uuid.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), ForeignKey('units_nodes.uuid', ondelete='CASCADE'), nullable=True)
    )

    # Repo, Unit, UnitNode
    resource_type: str = Field(nullable=False)
    resource_repo_uuid: pkg_uuid.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), ForeignKey('repos.uuid', ondelete='CASCADE'), nullable=True)
    )
    resource_unit_uuid: pkg_uuid.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), ForeignKey('units.uuid', ondelete='CASCADE'), nullable=True)
    )
    resource_unit_node_uuid: pkg_uuid.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), ForeignKey('units_nodes.uuid', ondelete='CASCADE'), nullable=True)
    )


class PermissionBaseType(BaseModel):
    agent_uuid: Optional[pkg_uuid.UUID] = None
    agent_type: Optional[PermissionEntities] = None

    resource_uuid: Optional[pkg_uuid.UUID] = None
    resource_type: Optional[PermissionEntities] = None
