import uuid as pkg_uuid

from sqlmodel import SQLModel, Field


class Permission(SQLModel, table=True):
    """Репозиторий"""

    __tablename__ = 'permissions'

    uuid: pkg_uuid.UUID = Field(primary_key=True, nullable=False, index=True, default_factory=pkg_uuid.uuid4)

    # uuid агента Unit или User
    agent_uuid: pkg_uuid.UUID = Field(nullable=False, index=True)
    # uuid ресурса Repo, Unit, User
    resource_uuid: pkg_uuid.UUID = Field(nullable=False, index=True)
