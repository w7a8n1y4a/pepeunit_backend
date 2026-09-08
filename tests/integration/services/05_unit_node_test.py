import json
import logging
import os
import time
import uuid as uuid_pkg

import pytest

from app import settings
from app.configs.errors import DataPipeError, UnitNodeError, ValidationError
from app.dto.enum import (
    GlobalPrefixTopic,
    ProcessingPolicyType,
    UnitNodeTypeEnum,
    VisibilityLevel,
)
from app.schemas.pydantic.unit_node import (
    DataPipeFilter,
    UnitNodeEdgeCreate,
    UnitNodeFilter,
    UnitNodeUpdate,
)
from app.utils.utils import create_upload_file_from_path
from tests.integration.helpers.data_pipe import upload_pipe_csv
from tests.integration.helpers.http import patch_input_state, post_schema_update
from tests.integration.helpers.services import (
    repo_service,
    unit_node_service,
    unit_service,
)
from tests.integration.helpers.wait import wait_until


async def test_update_unit_node(chain_sink_unit, regular_user_token, database, cc) -> None:
    service = unit_node_service(database, cc, regular_user_token)
    count, input_unit_node = service.list(
        UnitNodeFilter(unit_uuid=chain_sink_unit.uuid, type=[UnitNodeTypeEnum.INPUT])
    )

    assert input_unit_node[0].max_connections == 10

    update_unit_node = await service.update(
        input_unit_node[0].uuid,
        UnitNodeUpdate(visibility_level=VisibilityLevel.PRIVATE),
    )
    assert update_unit_node.visibility_level == VisibilityLevel.PRIVATE

    update_unit_node = await service.update(
        input_unit_node[0].uuid, UnitNodeUpdate(is_rewritable_input=True)
    )
    assert update_unit_node.is_rewritable_input

    update_unit_node = await service.update(
        input_unit_node[0].uuid, UnitNodeUpdate(max_connections=5)
    )
    assert update_unit_node.max_connections == 5

    count, output_unit_node = service.list(
        UnitNodeFilter(unit_uuid=chain_sink_unit.uuid, type=[UnitNodeTypeEnum.OUTPUT])
    )
    update_unit_node = await service.update(
        output_unit_node[0].uuid, UnitNodeUpdate(max_connections=3)
    )
    assert update_unit_node.max_connections == 3

    with pytest.raises(UnitNodeError):
        await service.update(
            output_unit_node[0].uuid, UnitNodeUpdate(is_rewritable_input=True)
        )

    with pytest.raises(UnitNodeError):
        await service.update(
            input_unit_node[0].uuid, UnitNodeUpdate(max_connections=0)
        )


@pytest.mark.datapipe
async def test_set_data_pipe(piped_units, regular_user_token, database, cc) -> None:
    service = unit_node_service(database, cc, regular_user_token)
    _, output_unit_node = service.list(
        UnitNodeFilter(
            unit_uuid=piped_units.universal_manual_unit.uuid,
            type=[UnitNodeTypeEnum.OUTPUT],
        )
    )
    assert output_unit_node[0].is_data_pipe_active

    bad_yml = "tests/data/yaml/integra/data_pipe_bad.yaml"
    data = await service.check_data_pipe_config(
        (await create_upload_file_from_path(bad_yml))
    )
    assert len(data) == 2

    data = await service.check_data_pipe_config(
        (await create_upload_file_from_path("tests/data/yaml/integra/data_pipe_aggregation.yaml"))
    )
    assert len(data) == 0


@pytest.mark.datapipe
async def test_get_data_pipe_config(
    piped_units,
    universal_manual_unit,
    compile_unit,
    regular_user_token,
    database,
    cc,
) -> None:
    service = unit_node_service(database, cc, regular_user_token)

    _, output_unit_node = service.list(
        UnitNodeFilter(unit_uuid=universal_manual_unit.uuid, type=[UnitNodeTypeEnum.OUTPUT])
    )
    config_path = service.get_data_pipe_config(output_unit_node[0].uuid)
    assert len(config_path) > 0
    os.remove(config_path)

    with pytest.raises(DataPipeError):
        _, output_unit_node = service.list(
            UnitNodeFilter(unit_uuid=compile_unit.uuid, type=[UnitNodeTypeEnum.OUTPUT])
        )
        target_unit_node = output_unit_node[0]
        target_unit_node.is_data_pipe_active = True
        target_unit_node.data_pipe_yml = None
        service.unit_node_repository.update(target_unit_node.uuid, target_unit_node)
        service.get_data_pipe_config(target_unit_node.uuid)

    with pytest.raises(DataPipeError):
        _, output_unit_node = service.list(
            UnitNodeFilter(unit_uuid=compile_unit.uuid, type=[UnitNodeTypeEnum.OUTPUT])
        )
        target_unit_node = output_unit_node[0]
        target_unit_node.is_data_pipe_active = False
        service.unit_node_repository.update(target_unit_node.uuid, target_unit_node)
        service.get_data_pipe_config(output_unit_node[0].uuid)


def test_create_unit_node_edge(
    running_units, chain_edges, regular_user_token, database, cc
) -> None:
    token = regular_user_token
    target_units = running_units.chain()
    marked = time.time()

    def schemas_applied() -> bool:
        pending = False
        for unit in target_units:
            path = f"tmp/test_units/{unit.uuid}/schema.json"
            if not os.path.exists(path) or os.path.getmtime(path) < marked:
                post_schema_update(token, unit.uuid)
                pending = True
        return not pending

    wait_until(
        schemas_applied,
        timeout=40,
        interval=2,
        message="schema.json was not refreshed after SchemaUpdate",
    )

    service = unit_node_service(database, cc, token)
    _, source_inputs = service.list(
        UnitNodeFilter(unit_uuid=target_units[0].uuid, type=[UnitNodeTypeEnum.INPUT])
    )
    _, source_outputs = service.list(
        UnitNodeFilter(unit_uuid=target_units[0].uuid, type=[UnitNodeTypeEnum.OUTPUT])
    )
    source_input_uuid = source_inputs[0].uuid
    source_output_uuid = source_outputs[0].uuid

    state = "0"
    wait_until(
        lambda: patch_input_state(token, source_input_uuid, state) < 400,
        timeout=20,
        message="chain source input rejected set_state",
    )
    assert patch_input_state(token, source_output_uuid, state) >= 400

    def chain_arrived() -> bool:
        ready = True
        for unit in target_units:
            filepath = f"tmp/test_units/{unit.uuid}/log_state.json"
            if not os.path.exists(filepath):
                ready = False
                continue
            with open(filepath) as handle:
                if json.loads(handle.read())["value"] != 0:
                    ready = False
        if not ready:
            patch_input_state(token, source_input_uuid, state)
        return ready

    wait_until(
        chain_arrived,
        timeout=30,
        interval=2,
        message="MQTT chain did not write log_state.json",
    )


def test_duplicate_unit_node_edge(
    running_units, chain_edges, regular_user_token, database, cc
) -> None:
    service = unit_node_service(database, cc, regular_user_token)
    with pytest.raises(UnitNodeError):
        service.create_node_edge(
            UnitNodeEdgeCreate(
                node_output_uuid=chain_edges[0][1].uuid,
                node_input_uuid=chain_edges[1][0].uuid,
            )
        )


async def test_set_state_input_unit_node(
    running_units, compile_unit, regular_user_token, database, cc
) -> None:
    service = unit_node_service(database, cc, regular_user_token)
    unit_svc = unit_service(database, cc, regular_user_token)
    unit_token = unit_svc.generate_token(compile_unit.uuid)

    count, unit_nodes = service.list(
        UnitNodeFilter(unit_uuid=compile_unit.uuid, type=[UnitNodeTypeEnum.INPUT])
    )
    node_uuid = unit_nodes[0].uuid
    state = "test"
    assert patch_input_state(unit_token, node_uuid, state) >= 400

    await service.update(node_uuid, UnitNodeUpdate(is_rewritable_input=True))
    wait_until(
        lambda: patch_input_state(unit_token, node_uuid, state) < 400,
        timeout=15,
        message="unit token still cannot set input after is_rewritable_input=True",
    )


def test_get_unit_node_edge(
    running_units, chain_edges, chain_middle_unit, regular_user_token, database, cc
) -> None:
    service = unit_node_service(database, cc, regular_user_token)
    count, target_edges = service.get_unit_node_edges(chain_middle_unit.uuid)
    assert len(target_edges) == 2


async def test_max_connections_blocks_edge(
    running_units,
    last_value_unit,
    n_records_unit,
    time_window_unit,
    regular_user_token,
    database,
    cc,
) -> None:
    service = unit_node_service(database, cc, regular_user_token)

    def _io(unit):
        _, inputs = service.list(
            UnitNodeFilter(unit_uuid=unit.uuid, type=[UnitNodeTypeEnum.INPUT])
        )
        _, outputs = service.list(
            UnitNodeFilter(unit_uuid=unit.uuid, type=[UnitNodeTypeEnum.OUTPUT])
        )
        return inputs[0], outputs[0]

    sink_input, _ = _io(n_records_unit)
    _, source_a = _io(last_value_unit)
    _, source_b = _io(time_window_unit)
    original_max = sink_input.max_connections
    created = None
    try:
        await service.update(sink_input.uuid, UnitNodeUpdate(max_connections=1))
        created = service.create_node_edge(
            UnitNodeEdgeCreate(
                node_output_uuid=source_a.uuid,
                node_input_uuid=sink_input.uuid,
            )
        )
        with pytest.raises(UnitNodeError):
            service.create_node_edge(
                UnitNodeEdgeCreate(
                    node_output_uuid=source_b.uuid,
                    node_input_uuid=sink_input.uuid,
                )
            )
    finally:
        if created:
            service.delete_node_edge(sink_input.uuid, source_a.uuid)
        await service.update(
            sink_input.uuid, UnitNodeUpdate(max_connections=original_max)
        )


def test_delete_unit_node_edge(
    running_units, chain_edges, chain_middle_unit, regular_user_token, database, cc
) -> None:
    service = unit_node_service(database, cc, regular_user_token)
    count, target_edges = service.get_unit_node_edges(chain_middle_unit.uuid)
    target_edge = target_edges[0]
    service.delete_node_edge(target_edge.node_input_uuid, target_edge.node_output_uuid)

    with pytest.raises(ValidationError):
        service.delete_node_edge(uuid_pkg.uuid4(), uuid_pkg.uuid4())


def test_get_many_unit_node(live_units, regular_user_token, database, cc) -> None:
    service = unit_node_service(database, cc, regular_user_token)
    count, units_nodes = service.list(
        UnitNodeFilter(
            search_string="input",
            type=[UnitNodeTypeEnum.INPUT],
            offset=0,
            limit=settings.pu_max_pagination_size,
        )
    )
    assert count >= 8
    assert len(units_nodes) == min(count, settings.pu_max_pagination_size)


async def test_data_pipe_requires_pepeunit_suffix(
    crud_unit, regular_user_token, database, cc
) -> None:
    service = unit_node_service(database, cc, regular_user_token)
    _, nodes = service.list(
        UnitNodeFilter(unit_uuid=crud_unit.uuid, type=[UnitNodeTypeEnum.INPUT])
    )
    target = nodes[0]
    original_topic = target.topic_name
    suffix = GlobalPrefixTopic.BACKEND_SUB_PREFIX.value
    stripped = (
        original_topic[: -len(suffix)]
        if original_topic.endswith(suffix)
        else original_topic
    )
    target.topic_name = stripped or "input"
    service.unit_node_repository.update(target.uuid, target)
    try:
        with pytest.raises(DataPipeError):
            await service.update(
                target.uuid, UnitNodeUpdate(is_data_pipe_active=True)
            )
    finally:
        restored = service.get(target.uuid)
        restored.topic_name = original_topic
        service.unit_node_repository.update(restored.uuid, restored)


def test_delete_unit(crud_unit, regular_user_token, database, cc) -> None:
    service = unit_service(database, cc, regular_user_token)
    service.delete(crud_unit.uuid)
    with pytest.raises(ValidationError):
        service.get(crud_unit.uuid)


def test_get_repo_versions(
    live_units, universal_private_repo, regular_user_token, database, cc
) -> None:
    service = repo_service(database, cc, regular_user_token)
    versions = service.get_versions(universal_private_repo.uuid)
    assert versions.unit_count == 3


@pytest.mark.datapipe
@pytest.mark.last_value
async def test_get_data_pipe_last_value(
    piped_units, regular_user_token, database, cc
) -> None:
    service = unit_node_service(database, cc, regular_user_token)
    _, output_last = service.list(
        UnitNodeFilter(
            unit_uuid=piped_units.last_value_unit.uuid, type=[UnitNodeTypeEnum.OUTPUT]
        )
    )
    wait_until(
        lambda: service.get(uuid=output_last[0].uuid).state is not None,
        timeout=20,
        message="last_value pipe did not write unit_node.state",
        session=database,
    )


@pytest.mark.datapipe
async def test_get_data_pipe_data(
    piped_units, regular_user_token, database, cc
) -> None:
    service = unit_node_service(database, cc, regular_user_token)

    _, output_n = service.list(
        UnitNodeFilter(
            unit_uuid=piped_units.n_records_unit.uuid, type=[UnitNodeTypeEnum.OUTPUT]
        )
    )
    wait_until(
        lambda: service.get_data_pipe_data(
            DataPipeFilter(uuid=output_n[0].uuid, type=ProcessingPolicyType.N_RECORDS)
        )[0]
        > 0,
        timeout=20,
        message="n_records pipe did not write ClickHouse rows",
    )

    _, output_tw = service.list(
        UnitNodeFilter(
            unit_uuid=piped_units.time_window_unit.uuid, type=[UnitNodeTypeEnum.OUTPUT]
        )
    )
    wait_until(
        lambda: service.get_data_pipe_data(
            DataPipeFilter(
                uuid=output_tw[0].uuid, type=ProcessingPolicyType.TIME_WINDOW
            )
        )[0]
        > 0,
        timeout=20,
        message="time_window pipe did not write ClickHouse rows",
    )


@pytest.mark.datapipe
async def test_get_data_pipe_data_csv(
    piped_units, n_records_unit, regular_user_token, database, cc
) -> None:
    service = unit_node_service(database, cc, regular_user_token)
    _, output_unit_node = service.list(
        UnitNodeFilter(unit_uuid=n_records_unit.uuid, type=[UnitNodeTypeEnum.OUTPUT])
    )
    file_path = service.get_data_pipe_data_csv(output_unit_node[0].uuid)
    os.remove(file_path)

    _, last_output = service.list(
        UnitNodeFilter(
            unit_uuid=piped_units.last_value_unit.uuid,
            type=[UnitNodeTypeEnum.OUTPUT],
        )
    )
    with pytest.raises(DataPipeError):
        service.get_data_pipe_data_csv(last_output[0].uuid)


@pytest.mark.datapipe
async def test_delete_data_pipe_data(
    piped_units, regular_user_token, database, cc
) -> None:
    service = unit_node_service(database, cc, regular_user_token)
    clickhouse_units = [
        (piped_units.universal_manual_unit, ProcessingPolicyType.AGGREGATION),
        (piped_units.n_records_unit, ProcessingPolicyType.N_RECORDS),
        (piped_units.time_window_unit, ProcessingPolicyType.TIME_WINDOW),
    ]
    for target_unit, policy in clickhouse_units:
        # emulators publish to output/pepeunit only, so an input node gets no
        # rows while ClickHouse applies the delete mutation
        _, input_unit_node = service.list(
            UnitNodeFilter(unit_uuid=target_unit.uuid, type=[UnitNodeTypeEnum.INPUT])
        )
        node_uuid = input_unit_node[0].uuid

        await upload_pipe_csv(service, node_uuid, policy)
        filled_count, _ = service.get_data_pipe_data(
            DataPipeFilter(uuid=node_uuid, type=policy)
        )
        assert filled_count > 0

        service.delete_data_pipe_data(node_uuid)
        wait_until(
            lambda node_uuid=node_uuid, policy=policy: service.get_data_pipe_data(
                DataPipeFilter(uuid=node_uuid, type=policy)
            )[0]
            == 0,
            timeout=15,
            interval=0.5,
            message=f"{policy} rows were not deleted from ClickHouse",
        )

    _, last_output = service.list(
        UnitNodeFilter(
            unit_uuid=piped_units.last_value_unit.uuid,
            type=[UnitNodeTypeEnum.OUTPUT],
        )
    )
    service.delete_data_pipe_data(last_output[0].uuid)
    count, _ = service.get_data_pipe_data(
        DataPipeFilter(
            uuid=last_output[0].uuid, type=ProcessingPolicyType.LAST_VALUE
        )
    )
    assert count == 1
