import uuid as uuid_pkg

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


class Resource(BaseModel):
    resource_uuid: uuid_pkg.UUID
    resource_type: PermissionEntities
