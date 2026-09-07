import uuid as uuid_pkg

import pytest

from app.configs.errors import CustomPermissionError, NoAccessError, ValidationError
from app.dto.enum import PermissionEntities, UnitNodeTypeEnum, VisibilityLevel
from app.schemas.pydantic.permission import PermissionCreate, PermissionFilter
from app.schemas.pydantic.repo import RepoFilter
from app.schemas.pydantic.unit import UnitFilter
from app.schemas.pydantic.unit_node import UnitNodeFilter
from tests.integration.helpers.services import (
    permission_service,
    repo_service,
    unit_node_service,
    unit_service,
)


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
        PermissionFilter.unlimited(
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


def test_visibility_get_matrix(
    live_units,
    extra_user_token,
    database,
    cc,
) -> None:
    extra_units = unit_service(database, cc, extra_user_token)
    extra_units.get(live_units.universal_manual_unit.uuid)
    extra_units.get(live_units.n_records_unit.uuid)
    with pytest.raises(NoAccessError):
        extra_units.get(live_units.universal_auto_unit.uuid)


def test_visibility_list_hides_private(
    live_units, extra_user_token, database, cc
) -> None:
    extra_units = unit_service(database, cc, extra_user_token)
    _, units = extra_units.list(
        UnitFilter(uuids=[live_units.universal_auto_unit.uuid])
    )
    assert all(
        unit[0].uuid != live_units.universal_auto_unit.uuid for unit in units
    )


def test_bot_sees_only_public(
    live_repos, live_units, database, cc
) -> None:
    bot_repos = repo_service(database, cc, None)
    bot_repos.get(live_repos.universal_public_repo.uuid)
    with pytest.raises(NoAccessError):
        bot_repos.get(live_repos.universal_internal_repo.uuid)
    with pytest.raises(NoAccessError):
        bot_repos.get(live_repos.universal_private_repo.uuid)

    _, repos = bot_repos.list(RepoFilter.unlimited())
    assert all(
        repo.visibility_level == VisibilityLevel.PUBLIC for repo in repos
    )

    bot_units = unit_service(database, cc, None)
    bot_units.get(live_units.universal_manual_unit.uuid)
    with pytest.raises(NoAccessError):
        bot_units.get(live_units.universal_auto_unit.uuid)


def test_permission_grants_and_revokes_private_access(
    private_crud_unit,
    extra_user,
    extra_user_token,
    regular_user_token,
    database,
    cc,
) -> None:
    extra_units = unit_service(database, cc, extra_user_token)
    with pytest.raises(NoAccessError):
        extra_units.get(private_crud_unit.uuid)

    permissions = permission_service(database, regular_user_token)
    permissions.create(
        PermissionCreate(
            agent_uuid=extra_user.uuid,
            agent_type=PermissionEntities.USER,
            resource_uuid=private_crud_unit.uuid,
            resource_type=PermissionEntities.UNIT,
        )
    )
    assert extra_units.get(private_crud_unit.uuid).uuid == private_crud_unit.uuid
    _, units = extra_units.list(UnitFilter(uuids=[private_crud_unit.uuid]))
    assert any(unit[0].uuid == private_crud_unit.uuid for unit in units)

    permissions.delete(extra_user.uuid, private_crud_unit.uuid)
    with pytest.raises(NoAccessError):
        extra_units.get(private_crud_unit.uuid)


def test_create_permission_duplicate(
    private_crud_unit, extra_user, regular_user_token, database
) -> None:
    service = permission_service(database, regular_user_token)
    payload = PermissionCreate(
        agent_uuid=extra_user.uuid,
        agent_type=PermissionEntities.USER,
        resource_uuid=private_crud_unit.uuid,
        resource_type=PermissionEntities.UNIT,
    )
    service.create(payload)
    with pytest.raises(CustomPermissionError):
        service.create(payload)


def test_cannot_delete_creator_permission(
    crud_unit, regular_user, regular_user_token, database
) -> None:
    with pytest.raises(CustomPermissionError):
        permission_service(database, regular_user_token).delete(
            regular_user.uuid, crud_unit.uuid
        )


def test_cannot_delete_unit_self_permission(
    compile_unit, regular_user_token, database
) -> None:
    with pytest.raises(CustomPermissionError):
        permission_service(database, regular_user_token).delete(
            compile_unit.uuid, compile_unit.uuid
        )


def test_cannot_delete_unit_parent_repo_permission(
    compile_unit, regular_user_token, database
) -> None:
    with pytest.raises(CustomPermissionError):
        permission_service(database, regular_user_token).delete(
            compile_unit.uuid, compile_unit.repo_uuid
        )


def test_cannot_delete_unit_child_node_permission(
    compile_unit, regular_user_token, database, cc
) -> None:
    _, nodes = unit_node_service(database, cc, regular_user_token).list(
        UnitNodeFilter(unit_uuid=compile_unit.uuid, type=[UnitNodeTypeEnum.INPUT])
    )
    with pytest.raises(CustomPermissionError):
        permission_service(database, regular_user_token).delete(
            compile_unit.uuid, nodes[0].uuid
        )
