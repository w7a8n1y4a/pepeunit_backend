import uuid as uuid_pkg
from dataclasses import dataclass

from pydantic import BaseModel

from app.dto.enum import PermissionEntities
from app.schemas.pydantic.pagination import BasePaginationRestMixin


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


@dataclass
class PermissionFilter(BasePaginationRestMixin):
    resource_uuid: uuid_pkg.UUID
    resource_type: PermissionEntities
    agent_type: PermissionEntities | None = None

    def dict(self):
        return self.__dict__


class PermissionsRead(BaseModel):
    count: int
    permissions: list[PermissionRead]
