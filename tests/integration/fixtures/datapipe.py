import asyncio

import pytest

from app.dto.enum import UnitNodeTypeEnum
from app.schemas.pydantic.unit_node import UnitNodeFilter, UnitNodeUpdate
from app.utils.utils import create_upload_file_from_path
from tests.integration.helpers.services import unit_node_service

PIPE_YAMLS = {
    "universal_manual_unit": "tests/data/yaml/integra/data_pipe_aggregation.yaml",
    "last_value_unit": "tests/data/yaml/integra/data_pipe_last_value.yaml",
    "n_records_unit": "tests/data/yaml/integra/data_pipe_n_records.yaml",
    "time_window_unit": "tests/data/yaml/integra/data_pipe_time_window.yaml",
}


async def _activate_and_set_pipe(service, unit, yaml_path: str | None) -> None:
    for node_type in (UnitNodeTypeEnum.OUTPUT, UnitNodeTypeEnum.INPUT):
        _, nodes = service.list(UnitNodeFilter(unit_uuid=unit.uuid, type=[node_type]))
        await service.update(nodes[0].uuid, UnitNodeUpdate(is_data_pipe_active=True))
        if yaml_path:
            await service.set_data_pipe_config(
                nodes[0].uuid, (await create_upload_file_from_path(yaml_path))
            )


@pytest.fixture(scope="session")
def piped_units(running_units, regular_user_token, database, cc):
    service = unit_node_service(database, cc, regular_user_token)

    async def _setup() -> None:
        mapping = [
            (running_units.universal_manual_unit, PIPE_YAMLS["universal_manual_unit"]),
            (running_units.last_value_unit, PIPE_YAMLS["last_value_unit"]),
            (running_units.n_records_unit, PIPE_YAMLS["n_records_unit"]),
            (running_units.time_window_unit, PIPE_YAMLS["time_window_unit"]),
        ]
        for unit, yaml_path in mapping:
            await _activate_and_set_pipe(service, unit, yaml_path)

    asyncio.run(_setup())
    return running_units
