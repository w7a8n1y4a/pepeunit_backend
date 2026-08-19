import json
import logging
import os
import shutil
import zlib
from dataclasses import dataclass, fields

import pytest

from app.dto.enum import StaticRepoFileName, VisibilityLevel
from app.schemas.pydantic.unit import UnitCreate
from tests.integration.helpers.names import entity_name, unique_name
from tests.integration.helpers.services import (
    branch_commits,
    unit_service,
)
from tests.integration.helpers.wait import wait_until


def _create_manual_unit(database, cc, token, repo, name: str, *, compile_unit: bool = False):
    service = unit_service(database, cc, token)
    _, commits = branch_commits(database, token, repo.repository_registry_uuid)
    return service.create(
        UnitCreate(
            repo_uuid=repo.uuid,
            visibility_level=repo.visibility_level,
            name=name,
            is_auto_update_from_repo_unit=False,
            repo_branch=repo.default_branch,
            repo_commit=commits[0].commit,
            target_firmware_platform="Universal" if compile_unit else None,
        )
    )


def _create_auto_unit(database, cc, token, repo, name: str):
    return unit_service(database, cc, token).create(
        UnitCreate(
            repo_uuid=repo.uuid,
            visibility_level=repo.visibility_level,
            name=name,
            is_auto_update_from_repo_unit=True,
        )
    )


@dataclass
class LiveUnits:
    universal_auto_unit: object
    universal_manual_unit: object
    last_value_unit: object
    n_records_unit: object
    time_window_unit: object
    chain_source_unit: object
    chain_middle_unit: object
    chain_sink_unit: object
    compile_unit: object

    def all(self) -> list:
        return [getattr(self, item.name) for item in fields(self)]

    def firmware_manual(self) -> list:
        return [unit for unit in self.all() if unit is not self.universal_auto_unit]

    def chain(self) -> list:
        return [self.chain_source_unit, self.chain_middle_unit, self.chain_sink_unit]

    def piped(self) -> list:
        return [
            self.universal_manual_unit,
            self.last_value_unit,
            self.n_records_unit,
            self.time_window_unit,
        ]


@pytest.fixture(scope="session")
def live_units(live_repos, regular_user_token, database, cc) -> LiveUnits:
    token = regular_user_token
    service = unit_service(database, cc, token)

    units = LiveUnits(
        universal_auto_unit=_create_auto_unit(
            database, cc, token, live_repos.universal_private_repo, entity_name("u_auto")
        ),
        universal_manual_unit=_create_manual_unit(
            database, cc, token, live_repos.universal_public_repo, entity_name("u_man")
        ),
        last_value_unit=_create_manual_unit(
            database, cc, token, live_repos.universal_public_repo, entity_name("u_last")
        ),
        n_records_unit=_create_manual_unit(
            database, cc, token, live_repos.universal_internal_repo, entity_name("u_nrec")
        ),
        time_window_unit=_create_manual_unit(
            database, cc, token, live_repos.universal_private_repo, entity_name("u_twin")
        ),
        chain_source_unit=_create_manual_unit(
            database, cc, token, live_repos.universal_public_repo, entity_name("u_csrc")
        ),
        chain_middle_unit=_create_manual_unit(
            database, cc, token, live_repos.universal_internal_repo, entity_name("u_cmid")
        ),
        chain_sink_unit=_create_manual_unit(
            database, cc, token, live_repos.universal_private_repo, entity_name("u_csnk")
        ),
        compile_unit=_create_manual_unit(
            database,
            cc,
            token,
            live_repos.universal_compile_repo,
            entity_name("u_cmp"),
            compile_unit=True,
        ),
    )

    for unit in units.all():
        current_env = service.get_env(unit.uuid)
        service.set_env(unit.uuid, json.dumps(current_env))

    return units


@pytest.fixture(scope="session")
def universal_auto_unit(live_units):
    return live_units.universal_auto_unit


@pytest.fixture(scope="session")
def universal_manual_unit(live_units):
    return live_units.universal_manual_unit


@pytest.fixture(scope="session")
def last_value_unit(live_units):
    return live_units.last_value_unit


@pytest.fixture(scope="session")
def n_records_unit(live_units):
    return live_units.n_records_unit


@pytest.fixture(scope="session")
def time_window_unit(live_units):
    return live_units.time_window_unit


@pytest.fixture(scope="session")
def chain_source_unit(live_units):
    return live_units.chain_source_unit


@pytest.fixture(scope="session")
def chain_middle_unit(live_units):
    return live_units.chain_middle_unit


@pytest.fixture(scope="session")
def chain_sink_unit(live_units):
    return live_units.chain_sink_unit


@pytest.fixture(scope="session")
def compile_unit(live_units):
    return live_units.compile_unit


@pytest.fixture(scope="session")
def unpacked_firmwares(live_units, regular_user_token, database, cc) -> LiveUnits:
    service = unit_service(database, cc, regular_user_token)
    test_unit_path = "tmp/test_units"
    os.makedirs(test_unit_path, exist_ok=True)

    methods = [
        service.get_unit_firmware_zip,
        service.get_unit_firmware_tar,
        service.get_unit_firmware_tgz,
    ]
    leftovers = []

    for inc, unit in enumerate(live_units.all()):
        logging.info(unit.uuid)
        method_idx = inc % 3
        if method_idx == 2:
            tgz_path = methods[method_idx](unit.uuid, 9, 9)
            leftovers.append(tgz_path)
            with open(tgz_path, "rb") as handle:
                producer = zlib.decompressobj(wbits=9)
                tar_data = producer.decompress(handle.read()) + producer.flush()
            archive_path = f"tmp/{unit.uuid}.tar"
            with open(archive_path, "wb") as tar_file:
                tar_file.write(tar_data)
        else:
            archive_path = methods[method_idx](unit.uuid)

        leftovers.append(archive_path)
        unpack_path = f"{test_unit_path}/{unit.uuid}"
        shutil.unpack_archive(archive_path, unpack_path, "zip" if method_idx == 0 else "tar")

        with open(f"{unpack_path}/{StaticRepoFileName.ENV.value}") as handle:
            env_dict = json.loads(handle.read())
            assert len(env_dict["PU_AUTH_TOKEN"]) > 100

    for path in leftovers:
        os.remove(path)

    return live_units


@pytest.fixture(scope="session")
def running_units(unpacked_firmwares, client_emulator, regular_user_token, database, cc) -> LiveUnits:
    client_emulator.task_queue.put(unpacked_firmwares.all())
    service = unit_service(database, cc, regular_user_token)
    wait_until(
        lambda: all(
            service.get(unit.uuid).current_commit_version for unit in unpacked_firmwares.all()
        ),
        timeout=30,
        message="emulators did not report current_commit_version",
        session=database,
    )
    return unpacked_firmwares


@pytest.fixture(scope="session")
def chain_edges(running_units, regular_user_token, database, cc):
    from app.dto.enum import UnitNodeTypeEnum
    from app.schemas.pydantic.unit_node import UnitNodeEdgeCreate, UnitNodeFilter
    from tests.integration.helpers.services import unit_node_service

    service = unit_node_service(database, cc, regular_user_token)
    io_units_list = []
    for unit in running_units.chain():
        _, unit_nodes = service.list(UnitNodeFilter(unit_uuid=unit.uuid))
        if unit_nodes[0].type == UnitNodeTypeEnum.OUTPUT:
            unit_nodes = unit_nodes[::-1]
        io_units_list.append(unit_nodes)

    service.create_node_edge(
        UnitNodeEdgeCreate(
            node_output_uuid=io_units_list[0][1].uuid,
            node_input_uuid=io_units_list[1][0].uuid,
        )
    )
    service.create_node_edge(
        UnitNodeEdgeCreate(
            node_output_uuid=io_units_list[1][1].uuid,
            node_input_uuid=io_units_list[2][0].uuid,
        )
    )
    return io_units_list


def _create_crud_unit(database, cc, token, repo, visibility_level, name: str):
    read, commits = branch_commits(database, token, repo.repository_registry_uuid)
    return unit_service(database, cc, token).create(
        UnitCreate(
            repo_uuid=repo.uuid,
            visibility_level=visibility_level,
            name=name,
            is_auto_update_from_repo_unit=False,
            repo_branch=read.branches[0],
            repo_commit=commits[0].commit,
        )
    )


@pytest.fixture
def crud_unit(universal_public_repo, regular_user_token, database, cc):
    token = regular_user_token
    unit = _create_crud_unit(
        database,
        cc,
        token,
        universal_public_repo,
        VisibilityLevel.PUBLIC,
        unique_name("ucrud"),
    )
    yield unit
    try:
        unit_service(database, cc, token).delete(unit.uuid)
    except Exception:
        pass


@pytest.fixture
def private_crud_unit(universal_public_repo, regular_user_token, database, cc):
    token = regular_user_token
    unit = _create_crud_unit(
        database,
        cc,
        token,
        universal_public_repo,
        VisibilityLevel.PRIVATE,
        unique_name("upriv"),
    )
    yield unit
    try:
        unit_service(database, cc, token).delete(unit.uuid)
    except Exception:
        pass
