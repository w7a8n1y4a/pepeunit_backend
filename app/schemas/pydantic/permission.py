import uuid as uuid_pkg
from typing import Optional

from pydantic import BaseModel

from app.repositories.enum import PermissionEntities


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

    offset: Optional[int] = None
    limit: Optional[int] = None


class PermissionsRead(BaseModel):
    count: int
    permissions: list[PermissionRead]
