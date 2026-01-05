import json
import logging
import os
import time
import uuid as uuid_pkg

import httpx
import pytest

from app import settings
from app.configs.errors import DataPipeError, UnitNodeError, ValidationError
from app.configs.rest import get_repo_service, get_unit_node_service, get_unit_service
from app.dto.enum import ProcessingPolicyType, UnitNodeTypeEnum, VisibilityLevel
from app.schemas.pydantic.unit_node import (
    DataPipeFilter,
    UnitNodeEdgeCreate,
    UnitNodeFilter,
    UnitNodeSetState,
    UnitNodeUpdate,
)
from app.utils.utils import create_upload_file_from_path


@pytest.mark.run(order=0)
async def test_update_unit_node(database, cc) -> None:
    current_user = pytest.users[0]
    unit_node_service = get_unit_node_service(
        database, cc, pytest.user_tokens_dict[current_user.uuid]
    )

    target_unit = pytest.units[-2]

    count, input_unit_node = unit_node_service.list(
        UnitNodeFilter(unit_uuid=target_unit.uuid, type=[UnitNodeTypeEnum.INPUT])
    )

    # check default max_connections value is 10
    assert input_unit_node[0].max_connections == 10

    # check update visibility level
    update_unit_node = await unit_node_service.update(
        input_unit_node[0].uuid,
        UnitNodeUpdate(visibility_level=VisibilityLevel.PRIVATE),
    )
    assert update_unit_node.visibility_level == VisibilityLevel.PRIVATE

    # check update is_rewritable_input for input
    update_unit_node = await unit_node_service.update(
        input_unit_node[0].uuid, UnitNodeUpdate(is_rewritable_input=True)
    )
    assert update_unit_node.is_rewritable_input

    # check update max_connections for input node
    update_unit_node = await unit_node_service.update(
        input_unit_node[0].uuid, UnitNodeUpdate(max_connections=5)
    )
    assert update_unit_node.max_connections == 5

    # check update max_connections for output node
    count, output_unit_node = unit_node_service.list(
        UnitNodeFilter(unit_uuid=target_unit.uuid, type=[UnitNodeTypeEnum.OUTPUT])
    )
    update_unit_node = await unit_node_service.update(
        output_unit_node[0].uuid, UnitNodeUpdate(max_connections=3)
    )
    assert update_unit_node.max_connections == 3

    # check update is_rewritable_input for output
    with pytest.raises(UnitNodeError):
        update_unit_node = await unit_node_service.update(
            output_unit_node[0].uuid, UnitNodeUpdate(is_rewritable_input=True)
        )

    # check max_connections validation (must be at least 1)
    with pytest.raises(UnitNodeError):
        update_unit_node = await unit_node_service.update(
            input_unit_node[0].uuid, UnitNodeUpdate(max_connections=0)
        )

    # check set active data pipe config
    for target_unit in pytest.units[1:6]:
        count, output_unit_node = unit_node_service.list(
            UnitNodeFilter(unit_uuid=target_unit.uuid, type=[UnitNodeTypeEnum.OUTPUT])
        )

        update_unit_node = await unit_node_service.update(
            output_unit_node[0].uuid, UnitNodeUpdate(is_data_pipe_active=True)
        )
        assert update_unit_node.is_data_pipe_active

        # create only for grafana tests
        count, input_unit_node = unit_node_service.list(
            UnitNodeFilter(unit_uuid=target_unit.uuid, type=[UnitNodeTypeEnum.INPUT])
        )

        update_unit_node = await unit_node_service.update(
            input_unit_node[0].uuid, UnitNodeUpdate(is_data_pipe_active=True)
        )
        assert update_unit_node.is_data_pipe_active


@pytest.mark.run(order=1)
async def test_set_data_pipe(database, cc) -> None:
    current_user = pytest.users[0]
    unit_node_service = get_unit_node_service(
        database, cc, pytest.user_tokens_dict[current_user.uuid]
    )

    yml_files_list = [
        "tests/data/yaml/integra/data_pipe_aggregation.yaml",
        "tests/data/yaml/integra/data_pipe_last_value.yaml",
        "tests/data/yaml/integra/data_pipe_n_records.yaml",
        "tests/data/yaml/integra/data_pipe_time_window.yaml",
    ]

    # check set correct yaml
    for yml_file, target_unit in zip(yml_files_list, pytest.units[1:5]):
        count, output_unit_node = unit_node_service.list(
            UnitNodeFilter(unit_uuid=target_unit.uuid, type=[UnitNodeTypeEnum.OUTPUT])
        )

        await unit_node_service.set_data_pipe_config(
            output_unit_node[0].uuid, (await create_upload_file_from_path(yml_file))
        )

        # create only for grafana tests
        count, input_unit_node = unit_node_service.list(
            UnitNodeFilter(unit_uuid=target_unit.uuid, type=[UnitNodeTypeEnum.INPUT])
        )

        await unit_node_service.set_data_pipe_config(
            input_unit_node[0].uuid, (await create_upload_file_from_path(yml_file))
        )

    # check bad yaml
    bad_yml = "tests/data/yaml/integra/data_pipe_bad.yaml"
    data = await unit_node_service.check_data_pipe_config(
        (await create_upload_file_from_path(bad_yml))
    )

    assert len(data) == 2

    # check correct yaml
    data = await unit_node_service.check_data_pipe_config(
        (await create_upload_file_from_path(yml_files_list[0]))
    )

    assert len(data) == 0


@pytest.mark.run(order=2)
async def test_get_data_pipe_config(database, cc) -> None:
    current_user = pytest.users[0]
    unit_node_service = get_unit_node_service(
        database, cc, pytest.user_tokens_dict[current_user.uuid]
    )

    _, output_unit_node = unit_node_service.list(
        UnitNodeFilter(unit_uuid=pytest.units[1].uuid, type=[UnitNodeTypeEnum.OUTPUT])
    )

    # check get data pipe
    config_path = unit_node_service.get_data_pipe_config(output_unit_node[0].uuid)

    assert len(config_path) > 0
    os.remove(config_path)

    # check not filed active data pipe
    with pytest.raises(DataPipeError):

        _, output_unit_node = unit_node_service.list(
            UnitNodeFilter(
                unit_uuid=pytest.units[5].uuid, type=[UnitNodeTypeEnum.OUTPUT]
            )
        )

        target_unit_node = output_unit_node[0]
        target_unit_node.is_data_pipe_active = True
        target_unit_node.data_pipe_yml = None

        unit_node_service.unit_node_repository.update(target_unit_node.uuid, target_unit_node)

        unit_node_service.get_data_pipe_config(target_unit_node.uuid)

    # check not active data pipe get config
    with pytest.raises(DataPipeError):
        _, output_unit_node = unit_node_service.list(
            UnitNodeFilter(
                unit_uuid=pytest.units[6].uuid, type=[UnitNodeTypeEnum.OUTPUT]
            )
        )

        target_unit_node = output_unit_node[0]
        target_unit_node.is_data_pipe_active = False
        unit_node_service.unit_node_repository.update(target_unit_node.uuid, target_unit_node)

        unit_node_service.get_data_pipe_config(output_unit_node[0].uuid)


@pytest.mark.run(order=3)
def test_create_unit_node_edge(database, cc) -> None:
    current_user = pytest.users[0]
    token = pytest.user_tokens_dict[current_user.uuid]
    unit_node_service = get_unit_node_service(
        database, cc, pytest.user_tokens_dict[current_user.uuid]
    )

    target_units = pytest.units[-4:-1]

    def update_schema(token: str, unit_uuid: uuid_pkg.UUID) -> int:
        headers = {"accept": "application/json", "x-auth-token": token}

        url = f"{settings.pu_link_prefix_and_v1}/units/send_command_to_input_base_topic/{unit_uuid}?command=SchemaUpdate"

        # send over http, in tests not work mqtt pub and sub
        r = httpx.post(url=url, headers=headers)

        return r.status_code

    def set_input_state(token: str, unit_node_uuid: uuid_pkg.UUID, state: str) -> int:
        headers = {"accept": "application/json", "x-auth-token": token}

        url = f"{settings.pu_link_prefix_and_v1}/unit_nodes/set_state_input/{unit_node_uuid}"

        # send over http, in tests not work mqtt pub and sub
        r = httpx.patch(
            url=url, json=UnitNodeSetState(state=state).dict(), headers=headers
        )

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
        UnitNodeEdgeCreate(
            node_output_uuid=io_units_list[0][1].uuid,
            node_input_uuid=io_units_list[1][0].uuid,
        )
    )

    # output 1 unit to input 2 unit
    unit_node_service.create_node_edge(
        UnitNodeEdgeCreate(
            node_output_uuid=io_units_list[1][1].uuid,
            node_input_uuid=io_units_list[2][0].uuid,
        )
    )

    # test update schema 3 Unit
    for unit in target_units:
        logging.info(unit.uuid)

        inc = 0
        while True:
            try:
                assert update_schema(token, unit.uuid) == 204
                break
            except AssertionError:

                if inc > 10:
                    assert False

                time.sleep(1)

                inc += 1


    # sleep for update schema 3 unit
    time.sleep(2)

    # target value for chain unit
    state = "0"

    # run chain input set
    assert set_input_state(token, io_units_list[0][0].uuid, state) < 400

    # check set output state
    assert set_input_state(token, io_units_list[0][1].uuid, state) >= 400

    # sleep for chain transmission data
    time.sleep(10)

    # check value in units
    for unit in target_units:
        logging.info(unit.uuid)

        filepath = f"tmp/test_units/{unit.uuid}/log_state.json"

        assert os.path.exists(filepath)

        with open(filepath, "r") as f:
            log_dict = json.loads(f.read())

            assert log_dict["value"] == 0


@pytest.mark.run(order=4)
async def test_set_state_input_unit_node(database, cc) -> None:
    current_user = pytest.users[0]
    unit_node_service = get_unit_node_service(
        database, cc, pytest.user_tokens_dict[current_user.uuid]
    )

    target_unit = pytest.units[-4]
    unit_service = get_unit_service(
        database, cc, pytest.user_tokens_dict[current_user.uuid]
    )
    unit_token = unit_service.generate_token(target_unit.uuid)

    def set_input_state(token: str, unit_node_uuid: uuid_pkg.UUID, state: str) -> int:
        headers = {"accept": "application/json", "x-auth-token": token}

        url = f"{settings.pu_link_prefix_and_v1}/unit_nodes/set_state_input/{unit_node_uuid}"

        # send over http, in tests not work mqtt pub and sub
        r = httpx.patch(
            url=url, json=UnitNodeSetState(state=state).dict(), headers=headers
        )

        return r.status_code

    count, unit_nodes = unit_node_service.list(
        UnitNodeFilter(unit_uuid=target_unit.uuid, type=[UnitNodeTypeEnum.INPUT])
    )

    state = "test"

    # check set with is_rewritable_input=False
    assert set_input_state(unit_token, unit_nodes[0].uuid, state) >= 400

    await unit_node_service.update(
        unit_nodes[0].uuid, UnitNodeUpdate(is_rewritable_input=True)
    )

    # check set with is_rewritable_input=True
    assert set_input_state(unit_token, unit_nodes[0].uuid, state) < 400


@pytest.mark.run(order=5)
def test_get_unit_node_edge(database, cc) -> None:
    current_user = pytest.users[0]
    unit_node_service = get_unit_node_service(
        database, cc, pytest.user_tokens_dict[current_user.uuid]
    )

    target_unit = pytest.units[-3]

    # check get unit node edges by uuid unit
    count, target_edges = unit_node_service.get_unit_node_edges(target_unit.uuid)
    pytest.edges.extend(target_edges)

    assert len(target_edges) == 2


@pytest.mark.run(order=6)
def test_delete_unit_node_edge(database, cc) -> None:
    current_user = pytest.users[0]
    unit_node_service = get_unit_node_service(
        database, cc, pytest.user_tokens_dict[current_user.uuid]
    )
    target_edge = pytest.edges[0]

    # check del edge
    unit_node_service.delete_node_edge(
        target_edge.node_input_uuid, target_edge.node_output_uuid
    )

    # check del with invalid del
    with pytest.raises(ValidationError):
        unit_node_service.delete_node_edge(uuid_pkg.uuid4(), uuid_pkg.uuid4())


@pytest.mark.run(order=7)
def test_get_many_unit_node(database, cc) -> None:
    current_user = pytest.users[0]
    unit_node_service = get_unit_node_service(
        database, cc, pytest.user_tokens_dict[current_user.uuid]
    )

    # check many get with all filters
    count, units_nodes = unit_node_service.list(
        UnitNodeFilter(
            search_string="input",
            type=[UnitNodeTypeEnum.INPUT],
            offset=0,
            limit=settings.pu_max_pagination_size,
        )
    )
    assert len(units_nodes) >= 8


@pytest.mark.run(order=8)
def test_delete_unit(database, cc) -> None:
    current_user = pytest.users[0]
    unit_service = get_unit_service(
        database, cc, pytest.user_tokens_dict[current_user.uuid]
    )

    target_unit = pytest.units[0]

    # check del Unit
    unit_service.delete(target_unit.uuid)
    with pytest.raises(ValidationError):
        unit_service.get(target_unit.uuid)


@pytest.mark.run(order=9)
def test_get_repo_versions(database, cc) -> None:
    current_user = pytest.users[0]
    repo_service = get_repo_service(
        database, cc, pytest.user_tokens_dict[current_user.uuid]
    )

    target_repo = pytest.repos[6]

    # check get_versions
    versions = repo_service.get_versions(target_repo.uuid)
    assert versions.unit_count == 2


@pytest.mark.run(order=10)
async def test_get_data_pipe_data(database, cc) -> None:
    current_user = pytest.users[0]
    unit_node_service = get_unit_node_service(
        database, cc, pytest.user_tokens_dict[current_user.uuid]
    )

    # check data last value
    count, output_unit_node = unit_node_service.list(
        UnitNodeFilter(unit_uuid=pytest.units[2].uuid, type=[UnitNodeTypeEnum.OUTPUT])
    )

    # wait set data to db pg
    inc = 0
    while True:
        unit_node = unit_node_service.get(
            uuid=output_unit_node[0].uuid,
        )

        if unit_node.state is not None:
            break

        time.sleep(1)

        if inc > 10:
            assert False

        inc += 1

    # check data n_records
    count, output_unit_node = unit_node_service.list(
        UnitNodeFilter(unit_uuid=pytest.units[3].uuid, type=[UnitNodeTypeEnum.OUTPUT])
    )

    # wait set data to db сс
    inc = 0
    while True:
        count, _ = unit_node_service.get_data_pipe_data(
            DataPipeFilter(
                uuid=output_unit_node[0].uuid,
                type=ProcessingPolicyType.N_RECORDS,
            )
        )

        if count > 0:
            break

        time.sleep(1)

        if inc > 10:
            assert False

        inc += 1

    # check data time window
    count, output_unit_node = unit_node_service.list(
        UnitNodeFilter(unit_uuid=pytest.units[4].uuid, type=[UnitNodeTypeEnum.OUTPUT])
    )

    # wait set data to db сс
    inc = 0
    while True:
        count, _ = unit_node_service.get_data_pipe_data(
            DataPipeFilter(
                uuid=output_unit_node[0].uuid,
                type=ProcessingPolicyType.TIME_WINDOW,
            )
        )

        if count > 0:
            break

        time.sleep(1)

        if inc > 10:
            assert False

        inc += 1


@pytest.mark.run(order=11)
async def test_get_data_pipe_data_csv(database, cc) -> None:
    current_user = pytest.users[0]
    unit_node_service = get_unit_node_service(
        database, cc, pytest.user_tokens_dict[current_user.uuid]
    )

    # check get csv for n_records
    count, output_unit_node = unit_node_service.list(
        UnitNodeFilter(unit_uuid=pytest.units[3].uuid, type=[UnitNodeTypeEnum.OUTPUT])
    )

    file_path = unit_node_service.get_data_pipe_data_csv(output_unit_node[0].uuid)

    os.remove(file_path)


@pytest.mark.run(order=12)
async def test_delete_data_pipe_data(database, cc) -> None:
    current_user = pytest.users[0]
    unit_node_service = get_unit_node_service(
        database, cc, pytest.user_tokens_dict[current_user.uuid]
    )

    # check delete pipe data in cc
    for target_unit in pytest.units[1:6]:
        count, output_unit_node = unit_node_service.list(
            UnitNodeFilter(unit_uuid=target_unit.uuid, type=[UnitNodeTypeEnum.OUTPUT])
        )

        unit_node_service.delete_data_pipe_data(output_unit_node[0].uuid)
