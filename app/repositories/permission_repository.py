from fastapi import Depends
from sqlmodel import Session

from app.configs.db import get_session
from app.domain.permission_model import Permission


class PermissionRepository:
    db: Session

    def __init__(self, db: Session = Depends(get_session)) -> None:
        self.db = db

    def create(self, permission: Permission) -> Permission:
        self.db.add(permission)
        self.db.commit()
        self.db.refresh(permission)
        return permission

    def get_agent_permissions(self, permission: Permission) -> list[str]:
        permissions = self.db.query(Permission).filter(
            Permission.agent_uuid == permission.agent_uuid,
        )

        return [item.resource_uuid for item in permissions]

    def check(self, permission: Permission) -> bool:
        check = (
            self.db.query(Permission)
            .filter(
                Permission.agent_uuid == permission.agent_uuid, Permission.resource_uuid == permission.resource_uuid
            )
            .first()
        )

        return bool(check)
