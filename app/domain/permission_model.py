import uuid as pkg_uuid

from sqlmodel import SQLModel, Field


class Permission(SQLModel, table=True):
    """Доступы"""

    __tablename__ = 'permissions'

    uuid: pkg_uuid.UUID = Field(primary_key=True, nullable=False, index=True, default_factory=pkg_uuid.uuid4)

    agent_uuid: pkg_uuid.UUID = Field(nullable=False, index=True)
    # User, Unit, Unit Node
    agent_type: str = Field(nullable=False)

    resource_uuid: pkg_uuid.UUID = Field(nullable=False, index=True)
    # Repo, Unit, UnitNode
    resource_type: str = Field(nullable=False)
