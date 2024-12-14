import json
import logging
import os
import time
import uuid as uuid_pkg

import fastapi
import httpx
import pytest

from app import settings
from app.configs.gql import get_repo_service, get_unit_node_service, get_unit_service
from app.configs.sub_entities import InfoSubEntity
from app.repositories.enum import UnitNodeTypeEnum, VisibilityLevel
from app.schemas.pydantic.unit_node import (
    UnitNodeEdgeCreate,
    UnitNodeFilter,
    UnitNodeSetState,
    UnitNodeUpdate,
)


@pytest.mark.run(order=0)
def test_update_unit_node(database) -> None:

    current_user = pytest.users[0]
    unit_node_service = get_unit_node_service(
        InfoSubEntity({'db': database, 'jwt_token': pytest.user_tokens_dict[current_user.uuid]})
    )

    target_unit = pytest.units[-2]

    count, input_unit_node = unit_node_service.list(
        UnitNodeFilter(unit_uuid=target_unit.uuid, type=[UnitNodeTypeEnum.INPUT])
    )

    # check update visibility level
    update_unit_node = unit_node_service.update(
        input_unit_node[0].uuid, UnitNodeUpdate(visibility_level=VisibilityLevel.PRIVATE)
    )
    assert update_unit_node.visibility_level == VisibilityLevel.PRIVATE

    # check update is_rewritable_input for input
    update_unit_node = unit_node_service.update(input_unit_node[0].uuid, UnitNodeUpdate(is_rewritable_input=True))
    assert update_unit_node.is_rewritable_input == True

    count, output_unit_node = unit_node_service.list(
        UnitNodeFilter(unit_uuid=target_unit.uuid, type=[UnitNodeTypeEnum.OUTPUT])
    )

    # check update is_rewritable_input for output
    with pytest.raises(fastapi.HTTPException):
        update_unit_node = unit_node_service.update(output_unit_node[0].uuid, UnitNodeUpdate(is_rewritable_input=True))


@pytest.mark.run(order=1)
def test_create_unit_node_edge(database) -> None:

    current_user = pytest.users[0]
    token = pytest.user_tokens_dict[current_user.uuid]
    unit_node_service = get_unit_node_service(
        InfoSubEntity({'db': database, 'jwt_token': pytest.user_tokens_dict[current_user.uuid]})
    )

    target_units = pytest.units[-4:-1]

    def update_schema(token: str, unit_uuid: uuid_pkg.UUID) -> int:
        headers = {'accept': 'application/json', 'x-auth-token': token}

        url = f'{settings.backend_link_prefix_and_v1}/units/update_schema/{unit_uuid}'

        # send over http, in tests not work mqtt pub and sub
        r = httpx.post(url=url, headers=headers)

        return r.status_code

    def set_input_state(token: str, unit_node_uuid: uuid_pkg.UUID, state: str) -> int:
        headers = {'accept': 'application/json', 'x-auth-token': token}

        url = f'{settings.backend_link_prefix_and_v1}/unit_nodes/set_state_input/{unit_node_uuid}'

        # send over http, in tests not work mqtt pub and sub
        r = httpx.patch(url=url, json=UnitNodeSetState(state=state).dict(), headers=headers)

        return r.status_code

    io_units_list = []
    for unit in target_units:
        logging.info(unit.uuid)
        count, unit_nodes = unit_node_service.list(UnitNodeFilter(unit_uuid=unit.uuid))

        # first input, two output - [Input, Output]
        if unit_nodes[0].type == UnitNodeTypeEnum.OUTPUT:
            unit_nodes = unit_nodes[::-1]

        io_units_list.append(unit_nodes)

    # output 0 unit to input 1 unit
    unit_node_service.create_node_edge(
        UnitNodeEdgeCreate(node_output_uuid=io_units_list[0][1].uuid, node_input_uuid=io_units_list[1][0].uuid)
    )

    # output 1 unit to input 2 unit
    unit_node_service.create_node_edge(
        UnitNodeEdgeCreate(node_output_uuid=io_units_list[1][1].uuid, node_input_uuid=io_units_list[2][0].uuid)
    )

    # test update schema 3 Unit
    for unit in target_units:
        logging.info(unit.uuid)
        assert update_schema(token, unit.uuid) == 204

    # sleep for update schema 3 unit
    time.sleep(4)

    # target value for chain unit
    state = '0'

    # run chain input set
    assert set_input_state(token, io_units_list[0][0].uuid, state) < 400

    # check set output state
    assert set_input_state(token, io_units_list[0][1].uuid, state) >= 400

    # sleep for chain transmission data
    time.sleep(4)

    # check value in units
    for unit in target_units:
        logging.info(unit.uuid)

        filepath = f'tmp/test_units/{unit.uuid}/log.json'

        assert os.path.exists(filepath)

        with open(filepath, 'r') as f:
            log_dict = json.loads(f.read())

            assert log_dict['value'] == 0


@pytest.mark.run(order=2)
def test_set_state_input_unit_node(database) -> None:

    current_user = pytest.users[0]
    unit_node_service = get_unit_node_service(
        InfoSubEntity({'db': database, 'jwt_token': pytest.user_tokens_dict[current_user.uuid]})
    )

    target_unit = pytest.units[-4]
    unit_service = get_unit_service(
        InfoSubEntity({'db': database, 'jwt_token': pytest.user_tokens_dict[current_user.uuid]})
    )
    unit_token = unit_service.generate_token(target_unit.uuid)

    def set_input_state(token: str, unit_node_uuid: uuid_pkg.UUID, state: str) -> int:
        headers = {'accept': 'application/json', 'x-auth-token': token}

        url = f'{settings.backend_link_prefix_and_v1}/unit_nodes/set_state_input/{unit_node_uuid}'

        # send over http, in tests not work mqtt pub and sub
        r = httpx.patch(url=url, json=UnitNodeSetState(state=state).dict(), headers=headers)

        return r.status_code

    count, unit_nodes = unit_node_service.list(
        UnitNodeFilter(unit_uuid=target_unit.uuid, type=[UnitNodeTypeEnum.INPUT])
    )

    state = 'test'

    # check set with is_rewritable_input=False
    assert set_input_state(unit_token, unit_nodes[0].uuid, state) >= 400

    unit_node_service.update(unit_nodes[0].uuid, UnitNodeUpdate(is_rewritable_input=True))

    # check set with is_rewritable_input=True
    assert set_input_state(unit_token, unit_nodes[0].uuid, state) < 400


@pytest.mark.run(order=3)
def test_get_unit_node_edge(database) -> None:

    current_user = pytest.users[0]
    unit_node_service = get_unit_node_service(
        InfoSubEntity({'db': database, 'jwt_token': pytest.user_tokens_dict[current_user.uuid]})
    )

    target_unit = pytest.units[-3]

    # check get unit node edges by uuid unit
    count, target_edges = unit_node_service.get_unit_node_edges(target_unit.uuid)
    pytest.edges.extend(target_edges)

    assert len(target_edges) == 2


@pytest.mark.run(order=4)
def test_delete_unit_node_edge(database) -> None:

    current_user = pytest.users[0]
    unit_node_service = get_unit_node_service(
        InfoSubEntity({'db': database, 'jwt_token': pytest.user_tokens_dict[current_user.uuid]})
    )

    target_edge = pytest.edges[0]

    # check del edge
    unit_node_service.delete_node_edge(target_edge.node_input_uuid, target_edge.node_output_uuid)

    # check del with invalid del
    with pytest.raises(fastapi.HTTPException):
        unit_node_service.delete_node_edge(uuid_pkg.uuid4(), uuid_pkg.uuid4())


@pytest.mark.run(order=5)
def test_get_many_unit_node(database) -> None:

    current_user = pytest.users[0]
    unit_node_service = get_unit_node_service(
        InfoSubEntity({'db': database, 'jwt_token': pytest.user_tokens_dict[current_user.uuid]})
    )

    # check many get with all filters
    count, units_nodes = unit_node_service.list(
        UnitNodeFilter(search_string='pepeunit', type=[UnitNodeTypeEnum.INPUT], offset=0, limit=1_000_000)
    )
    assert len(units_nodes) >= 8


@pytest.mark.run(order=6)
def test_delete_unit(database) -> None:

    current_user = pytest.users[0]
    unit_service = get_unit_service(
        InfoSubEntity({'db': database, 'jwt_token': pytest.user_tokens_dict[current_user.uuid]})
    )

    target_unit = pytest.units[0]

    # check del Unit
    unit_service.delete(target_unit.uuid)
    with pytest.raises(fastapi.HTTPException):
        unit_service.get(target_unit.uuid)


@pytest.mark.run(order=7)
def test_get_repo_versions(database) -> None:
    current_user = pytest.users[0]
    repo_service = get_repo_service(
        InfoSubEntity({'db': database, 'jwt_token': pytest.user_tokens_dict[current_user.uuid]})
    )

    target_unit = pytest.repos[6]

    # check get_versions
    versions = repo_service.get_versions(target_unit.uuid)
    assert versions.unit_count == 2
