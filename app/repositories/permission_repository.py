from fastapi import Depends, HTTPException
from fastapi import status as http_status

from sqlmodel import Session

from app.configs.db import get_session
from app.domain.permission_model import Permission
from app.domain.repo_model import Repo
from app.domain.unit_model import Unit
from app.domain.unit_node_model import UnitNode
from app.domain.user_model import User
from app.repositories.enum import PermissionEntities


class PermissionRepository:
    db: Session

    def __init__(self, db: Session = Depends(get_session)) -> None:
        self.db = db

    def get(self, permission: Permission) -> Permission:

        return self.db.get(Permission, permission.uuid)

    def get_agent(self, permission: Permission):
        return self.db.get(eval(permission.agent_type), permission.agent_uuid)

    def get_resource(self, permission: Permission):
        return self.db.get(eval(permission.resource_type), permission.resource_uuid)

    def create(self, permission: Permission) -> Permission:
        self.db.add(permission)
        self.db.commit()
        self.db.refresh(permission)
        return permission

    def bulk_create(self, permissions: list[Permission]) -> None:
        self.db.bulk_save_objects(permissions)
        self.db.commit()

    def get_agent_resources(self, permission: Permission) -> list[str]:
        permissions = self.db.query(Permission).filter(
            Permission.agent_uuid == permission.agent_uuid,
        )

        if permission.resource_type:
            permissions = permissions.filter(Permission.resource_type == permission.resource_type)

        return permissions.all()

    def get_resource_agents(self, permission: Permission):
        permissions = self.db.query(Permission).filter(
            Permission.resource_uuid == permission.resource_uuid,
        )

        if permission.agent_type:
            permissions = permissions.filter(Permission.agent_type == permission.agent_type)

        return permissions.all()

    def check(self, permission: Permission) -> bool:
        check = (
            self.db.query(Permission)
            .filter(
                Permission.agent_uuid == permission.agent_uuid,
                Permission.resource_uuid == permission.resource_uuid
            )
            .first()
        )

        return bool(check)

    def delete(self, permission: Permission) -> None:
        self.db.query(Permission).filter(
            Permission.agent_uuid == permission.agent_uuid,
            Permission.resource_uuid == permission.resource_uuid
        ).delete()
        self.db.commit()

    def delete_by_resource(self, permission: Permission) -> None:
        self.db.query(Permission).filter(Permission.resource_uuid == permission.resource_uuid).delete()
        self.db.commit()

    def delete_by_agent(self, permission: Permission) -> None:
        self.db.query(Permission).filter(Permission.agent_uuid == permission.agent_uuid).delete()
        self.db.commit()

    @staticmethod
    def is_valid_agent_type(permission: Permission) -> None:

        entities = [item.value for item in PermissionEntities]
        entities.remove(PermissionEntities.REPO)

        if permission.agent_type not in entities:
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Agent type is invalid"
            )

    @staticmethod
    def is_valid_resource_type(permission: Permission) -> None:

        entities = [item.value for item in PermissionEntities]
        entities.remove(PermissionEntities.USER)

        if permission.resource_type not in entities:
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Resource type is invalid"
            )
