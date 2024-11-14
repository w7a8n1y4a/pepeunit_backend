import uuid as uuid_pkg

import fastapi
import pytest

from app.configs.gql import get_permission_service
from app.configs.sub_entities import InfoSubEntity
from app.repositories.enum import PermissionEntities
from app.schemas.pydantic.permission import PermissionCreate, PermissionFilter


@pytest.mark.run(order=0)
def test_create_permission(database) -> None:

    current_user = pytest.users[0]
    unit_permission_service = get_permission_service(
        InfoSubEntity({'db': database, 'jwt_token': pytest.user_tokens_dict[current_user.uuid]})
    )

    target_agent = pytest.users[1]
    target_resource = pytest.units[-1]

    new_permission = unit_permission_service.create(
        PermissionCreate(
            agent_uuid=target_agent.uuid,
            agent_type=PermissionEntities.USER,
            resource_uuid=target_resource.uuid,
            resource_type=PermissionEntities.UNIT,
        )
    )

    pytest.permissions.append(new_permission)

    # check invalid agent
    with pytest.raises(fastapi.HTTPException):
        unit_permission_service.create(
            PermissionCreate(
                agent_uuid=target_agent.uuid,
                agent_type=PermissionEntities.UNIT,
                resource_uuid=target_resource.uuid,
                resource_type=PermissionEntities.UNIT,
            )
        )

    # check invalid resource
    with pytest.raises(fastapi.HTTPException):
        unit_permission_service.create(
            PermissionCreate(
                agent_uuid=target_agent.uuid,
                agent_type=PermissionEntities.USER,
                resource_uuid=target_resource.uuid,
                resource_type=PermissionEntities.UNIT_NODE,
            )
        )


@pytest.mark.run(order=1)
def test_get_permission(database) -> None:

    current_user = pytest.users[0]
    unit_permission_service = get_permission_service(
        InfoSubEntity({'db': database, 'jwt_token': pytest.user_tokens_dict[current_user.uuid]})
    )

    target_resource = pytest.units[-1]

    # get resource agents
    count, target_agents = unit_permission_service.get_resource_agents(
        PermissionFilter(resource_uuid=target_resource.uuid, resource_type=PermissionEntities.UNIT)
    )

    assert len(target_agents) == 3

    # check get invalid resource agents
    with pytest.raises(fastapi.HTTPException):
        unit_permission_service.get_resource_agents(
            PermissionFilter(resource_uuid=target_resource.uuid, resource_type=PermissionEntities.USER)
        )


@pytest.mark.run(order=2)
def test_delete_permission(database) -> None:

    current_user = pytest.users[0]
    unit_permission_service = get_permission_service(
        InfoSubEntity({'db': database, 'jwt_token': pytest.user_tokens_dict[current_user.uuid]})
    )

    target_permission = pytest.permissions[0]

    # check delete permission
    unit_permission_service.delete(target_permission.uuid)

    # check del invalid permission
    with pytest.raises(fastapi.HTTPException):
        unit_permission_service.delete(uuid_pkg.uuid4())
