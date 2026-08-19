import uuid as uuid_pkg

import pytest

from app.configs.errors import ValidationError
from app.dto.enum import PermissionEntities
from app.schemas.pydantic.permission import PermissionCreate, PermissionFilter
from tests.integration.helpers.services import permission_service


def test_create_permission(
    crud_unit, admin_user, regular_user_token, database
) -> None:
    service = permission_service(database, regular_user_token)
    new_permission = service.create(
        PermissionCreate(
            agent_uuid=admin_user.uuid,
            agent_type=PermissionEntities.USER,
            resource_uuid=crud_unit.uuid,
            resource_type=PermissionEntities.UNIT,
        )
    )
    assert new_permission.resource_uuid == crud_unit.uuid


def test_create_permission_invalid_agent(
    crud_unit, admin_user, regular_user_token, database
) -> None:
    service = permission_service(database, regular_user_token)
    with pytest.raises(ValidationError):
        service.create(
            PermissionCreate(
                agent_uuid=admin_user.uuid,
                agent_type=PermissionEntities.UNIT,
                resource_uuid=crud_unit.uuid,
                resource_type=PermissionEntities.UNIT,
            )
        )


def test_create_permission_invalid_resource(
    crud_unit, admin_user, regular_user_token, database
) -> None:
    service = permission_service(database, regular_user_token)
    with pytest.raises(ValidationError):
        service.create(
            PermissionCreate(
                agent_uuid=admin_user.uuid,
                agent_type=PermissionEntities.USER,
                resource_uuid=crud_unit.uuid,
                resource_type=PermissionEntities.UNIT_NODE,
            )
        )


def test_get_permission(crud_unit, regular_user_token, database) -> None:
    service = permission_service(database, regular_user_token)
    count, target_agents = service.get_resource_agents(
        PermissionFilter(
            resource_uuid=crud_unit.uuid, resource_type=PermissionEntities.UNIT
        )
    )
    assert len(target_agents) >= 2

    with pytest.raises(ValidationError):
        service.get_resource_agents(
            PermissionFilter(
                resource_uuid=crud_unit.uuid,
                resource_type=PermissionEntities.USER,
            )
        )


def test_delete_permission(
    crud_unit, admin_user, regular_user_token, database
) -> None:
    service = permission_service(database, regular_user_token)
    service.create(
        PermissionCreate(
            agent_uuid=admin_user.uuid,
            agent_type=PermissionEntities.USER,
            resource_uuid=crud_unit.uuid,
            resource_type=PermissionEntities.UNIT,
        )
    )
    service.delete(admin_user.uuid, crud_unit.uuid)

    with pytest.raises(ValidationError):
        service.delete(uuid_pkg.uuid4(), uuid_pkg.uuid4())
