import uuid as uuid_pkg

from pydantic import BaseModel

from app.dto.enum import PermissionEntities


class PermissionRead(BaseModel):
    uuid: uuid_pkg.UUID

    agent_uuid: uuid_pkg.UUID
    agent_type: PermissionEntities

    resource_uuid: uuid_pkg.UUID
    resource_type: PermissionEntities


class PermissionCreate(BaseModel):
    agent_uuid: uuid_pkg.UUID
    agent_type: PermissionEntities

    resource_uuid: uuid_pkg.UUID
    resource_type: PermissionEntities


class PermissionFilter(BaseModel):
    resource_uuid: uuid_pkg.UUID
    resource_type: PermissionEntities
    agent_type: PermissionEntities | None = None

    offset: int | None = None
    limit: int | None = None


class PermissionsRead(BaseModel):
    count: int
    permissions: list[PermissionRead]
