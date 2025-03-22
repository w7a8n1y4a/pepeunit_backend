import uuid as uuid_pkg
from typing import Optional

from fastapi import Depends
from sqlalchemy import or_
from sqlmodel import Session

from app.configs.db import get_session
from app.configs.errors import CustomPermissionError
from app.domain.permission_model import Permission, PermissionBaseType
from app.domain.repo_model import Repo
from app.domain.unit_model import Unit
from app.domain.unit_node_model import UnitNode
from app.domain.user_model import User
from app.dto.enum import PermissionEntities
from app.repositories.utils import apply_offset_and_limit
from app.schemas.pydantic.permission import PermissionFilter


class PermissionRepository:
    db: Session

    def __init__(self, db: Session = Depends(get_session)) -> None:
        self.db = db

    def get(self, permission: Permission) -> Optional[Permission]:
        return self.db.get(Permission, permission.uuid)

    def get_by_uuid(self, agent_uuid, resource_uuid):
        return (
            self.db.query(Permission)
            .filter(
                or_(
                    Permission.agent_user_uuid == agent_uuid,
                    Permission.agent_unit_uuid == agent_uuid,
                ),
                or_(
                    Permission.resource_repo_uuid == resource_uuid,
                    Permission.resource_unit_uuid == resource_uuid,
                    Permission.resource_unit_node_uuid == resource_uuid,
                ),
            )
            .first()
        )

    def get_agent(self, base_permission: PermissionBaseType):
        return self.db.get(eval(base_permission.agent_type), base_permission.agent_uuid)

    def get_resource(self, base_permission: PermissionBaseType):
        return self.db.get(eval(base_permission.resource_type), base_permission.resource_uuid)

    @staticmethod
    def base_type_to_domain(base_permission: PermissionBaseType) -> Permission:

        permission = Permission(agent_type=base_permission.agent_type, resource_type=base_permission.resource_type)

        agent_type = eval(base_permission.agent_type)
        if agent_type is User:
            permission.agent_user_uuid = base_permission.agent_uuid
        elif agent_type is Unit:
            permission.agent_unit_uuid = base_permission.agent_uuid

        resource_type = eval(base_permission.resource_type)
        if resource_type is Repo:
            permission.resource_repo_uuid = base_permission.resource_uuid
        elif resource_type is Unit:
            permission.resource_unit_uuid = base_permission.resource_uuid
        elif resource_type is UnitNode:
            permission.resource_unit_node_uuid = base_permission.resource_uuid

        return permission

    @staticmethod
    def domain_to_base_type(permission: Permission) -> PermissionBaseType:

        base_permission = PermissionBaseType(agent_type=permission.agent_type, resource_type=permission.resource_type)

        if permission.uuid:
            base_permission.uuid = permission.uuid

        agent_type = eval(base_permission.agent_type)
        if agent_type is User:
            base_permission.agent_uuid = permission.agent_user_uuid
        elif agent_type is Unit:
            base_permission.agent_uuid = permission.agent_unit_uuid

        resource_type = eval(base_permission.resource_type)
        if resource_type is Repo:
            base_permission.resource_uuid = permission.resource_repo_uuid
        elif resource_type is Unit:
            base_permission.resource_uuid = permission.resource_unit_uuid
        elif resource_type is UnitNode:
            base_permission.resource_uuid = permission.resource_unit_node_uuid

        return base_permission

    def create(self, base_permission: PermissionBaseType) -> PermissionBaseType:

        permission = self.base_type_to_domain(base_permission)

        self.db.add(permission)
        self.db.commit()
        self.db.refresh(permission)
        return self.domain_to_base_type(permission)

    def bulk_save(self, base_permissions: list[PermissionBaseType]) -> None:
        self.db.bulk_save_objects([self.base_type_to_domain(permission) for permission in base_permissions])
        self.db.commit()

    @staticmethod
    def get_agent_fld_uuid_by_type(fld_type: PermissionEntities) -> uuid_pkg.UUID:
        entities_dict = {
            PermissionEntities.USER: Permission.agent_user_uuid,
            PermissionEntities.UNIT: Permission.agent_unit_uuid,
        }
        return entities_dict[fld_type]

    @staticmethod
    def get_resource_fld_uuid_by_type(fld_type: PermissionEntities) -> uuid_pkg.UUID:
        entities_dict = {
            PermissionEntities.REPO: Permission.resource_repo_uuid,
            PermissionEntities.UNIT: Permission.resource_unit_uuid,
            PermissionEntities.UNIT_NODE: Permission.resource_unit_node_uuid,
        }
        return entities_dict[fld_type]

    def get_agent_resources(self, base_permission: PermissionBaseType) -> list[PermissionBaseType]:

        permissions = self.db.query(Permission).filter(
            self.get_agent_fld_uuid_by_type(base_permission.agent_type) == base_permission.agent_uuid
        )

        if base_permission.resource_type:
            permissions = permissions.filter(Permission.resource_type == base_permission.resource_type)

        return [self.domain_to_base_type(permission) for permission in permissions.all()]

    def get_resource_agents(self, filters: PermissionFilter) -> tuple[int, list[PermissionBaseType]]:

        query = self.db.query(Permission).filter(
            self.get_resource_fld_uuid_by_type(filters.resource_type) == filters.resource_uuid,
        )

        if filters.agent_type:
            query = query.filter(Permission.agent_type == filters.agent_type)

        count, query = apply_offset_and_limit(query, filters)

        return count, [self.domain_to_base_type(permission) for permission in query.all()]

    def check(self, base_permission: PermissionBaseType) -> bool:

        check = (
            self.db.query(Permission)
            .filter(
                self.get_agent_fld_uuid_by_type(base_permission.agent_type) == base_permission.agent_uuid,
                self.get_resource_fld_uuid_by_type(base_permission.resource_type) == base_permission.resource_uuid,
            )
            .first()
        )

        return bool(check)

    def delete(self, permission: Permission) -> None:
        self.db.delete(self.get(permission))
        self.db.commit()
        self.db.flush()

    @staticmethod
    def is_valid_agent_type(permission: Permission) -> None:

        entities = [item.value for item in PermissionEntities]
        entities.remove(PermissionEntities.REPO)
        entities.remove(PermissionEntities.UNIT_NODE)

        if permission.agent_type not in entities:
            raise CustomPermissionError(
                'Agent type {} is invalid, available: {}'.format(permission.agent_type, ', '.join(entities))
            )

    @staticmethod
    def is_valid_resource_type(permission: Permission) -> None:

        entities = [item.value for item in PermissionEntities]
        entities.remove(PermissionEntities.USER)

        if permission.resource_type not in entities:
            raise CustomPermissionError(
                'Resource type {} is invalid, available: {}'.format(permission.resource_type, ', '.join(entities))
            )
