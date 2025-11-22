import copy
import json
import logging
import os
import shutil
import time
import zlib

import httpx
import pytest

from app import settings
from app.configs.clickhouse import get_clickhouse_client
from app.configs.errors import (
    CipherError,
    GitRepoError,
    NoAccessError,
    UnitError,
    ValidationError,
)
from app.configs.rest import (
    get_repo_service,
    get_repository_registry_service,
    get_unit_service,
)
from app.domain.repo_model import Repo
from app.dto.enum import BackendTopicCommand, StaticRepoFileName, VisibilityLevel, ReservedEnvVariableName
from app.repositories.unit_log_repository import UnitLogRepository
from app.schemas.pydantic.repo import RepoUpdate
from app.schemas.pydantic.repository_registry import CommitFilter
from app.schemas.pydantic.unit import UnitCreate, UnitFilter, UnitLogFilter, UnitUpdate
from app.utils.utils import aes_gcm_encode


@pytest.mark.run(order=0)
def test_create_unit(database, cc) -> None:
    current_user = pytest.users[0]
    unit_service = get_unit_service(
        database, cc, pytest.user_tokens_dict[current_user.uuid]
    )
    repository_registry_service = get_repository_registry_service(
        database, pytest.user_tokens_dict[current_user.uuid]
    )

    # create auto updated unit
    new_units = []
    for inc, test_repo in enumerate(pytest.repos[-2:-1]):
        logging.info(test_repo.uuid)
        unit = unit_service.create(
            UnitCreate(
                repo_uuid=test_repo.uuid,
                visibility_level=test_repo.visibility_level,
                name=f"test_{inc}_{pytest.test_hash}",
                is_auto_update_from_repo_unit=True,
            )
        )
        new_units.append(unit)

    # create no auto updated units, with all visibility levels
    for inc, test_repo in enumerate(
        [pytest.repos[-4]] + pytest.repos[-4:-1] * 2 + [pytest.repos[-1]]
    ):
        logging.info(test_repo.uuid)
        repository_registry = (
            repository_registry_service.mapper_registry_to_registry_read(
                repository_registry_service.get(test_repo.repository_registry_uuid)
            )
        )
        commits = repository_registry_service.get_branch_commits(
            repository_registry.uuid,
            CommitFilter(repo_branch=repository_registry.branches[0]),
        )

        unit = unit_service.create(
            UnitCreate(
                repo_uuid=test_repo.uuid,
                visibility_level=test_repo.visibility_level,
                name=f"test_{inc + 1}_{pytest.test_hash}",
                is_auto_update_from_repo_unit=False,
                repo_branch=repository_registry.branches[0],
                repo_commit=commits[0].commit,
                target_firmware_platform="Universal"
                if test_repo.is_compilable_repo
                else None,
            )
        )
        new_units.append(unit)

    pytest.units = new_units

    # check create unit with exist name
    with pytest.raises(UnitError):
        test_repo = pytest.repos[-1]

        unit_service.create(
            UnitCreate(
                repo_uuid=test_repo.uuid,
                visibility_level=test_repo.visibility_level,
                name=f"test_0_{pytest.test_hash}",
                is_auto_update_from_repo_unit=True,
            )
        )

    # check create Unit with Repo without default branch
    repo_service = get_repo_service(
        database, cc, pytest.user_tokens_dict[current_user.uuid]
    )
    target_repo = Repo(**pytest.repos[0].__dict__)
    target_repo.default_branch = None
    repo_service.repo_repository.update(pytest.repos[0].uuid, target_repo)

    with pytest.raises(GitRepoError):
        test_repo = pytest.repos[0]

        unit_service.create(
            UnitCreate(
                repo_uuid=test_repo.uuid,
                visibility_level=test_repo.visibility_level,
                name=f"test_a_{pytest.test_hash}",
                is_auto_update_from_repo_unit=True,
            )
        )

    # check create without env_example and schema_example.json
    with pytest.raises(GitRepoError):
        test_repo = pytest.repos[0]

        unit_service.create(
            UnitCreate(
                repo_uuid=test_repo.uuid,
                visibility_level=test_repo.visibility_level,
                name=f"test_b_{pytest.test_hash}",
                is_auto_update_from_repo_unit=True,
            )
        )


@pytest.mark.run(order=1)
def test_delete_repo_with_unit(database, cc) -> None:
    current_user = pytest.users[0]
    repo_service = get_repo_service(
        database, cc, pytest.user_tokens_dict[current_user.uuid]
    )
    # test del repo with Unit
    with pytest.raises(ValidationError):
        repo_service.delete(pytest.repos[-1].uuid)


@pytest.mark.run(order=2)
def test_update_unit(database, cc) -> None:
    current_user = pytest.users[0]
    unit_service = get_unit_service(
        database, cc, pytest.user_tokens_dict[current_user.uuid]
    )
    repository_registry_service = get_repository_registry_service(
        database, pytest.user_tokens_dict[current_user.uuid]
    )

    # check change name to new
    test_unit = pytest.units[0]
    test_unit_name = test_unit.name + "test"
    unit_service.update(test_unit.uuid, UnitUpdate(name=test_unit_name))

    update_unit = unit_service.get(test_unit.uuid)

    assert test_unit_name == update_unit.name

    # change name to normal
    unit_service.update(test_unit.uuid, UnitUpdate(name=test_unit.name))

    # check change name when name is exist
    with pytest.raises(UnitError):
        unit_service.update(pytest.units[0].uuid, UnitUpdate(name=pytest.units[1].name))

    # check change visibility
    target_unit = pytest.units[1]
    logging.info(target_unit.uuid)

    unit_service.update(
        target_unit.uuid, UnitUpdate(visibility_level=VisibilityLevel.INTERNAL)
    )
    update_unit = unit_service.get(target_unit.uuid)
    assert update_unit.visibility_level == VisibilityLevel.INTERNAL

    unit_service.update(
        target_unit.uuid, UnitUpdate(visibility_level=VisibilityLevel.PUBLIC)
    )
    update_unit = unit_service.get(target_unit.uuid)
    assert update_unit.visibility_level == VisibilityLevel.PUBLIC

    # check set not auto update without commit and branch
    with pytest.raises(UnitError):
        unit_service.update(
            pytest.units[0].uuid, UnitUpdate(is_auto_update_from_repo_unit=False)
        )

    # check set hand update
    repo_service = get_repo_service(
        database, cc, pytest.user_tokens_dict[current_user.uuid]
    )

    target_unit = pytest.units[0]
    target_repo = repo_service.get(target_unit.repo_uuid)

    repository_registry = repository_registry_service.mapper_registry_to_registry_read(
        repository_registry_service.get(target_repo.repository_registry_uuid)
    )
    commits = repository_registry_service.get_branch_commits(
        repository_registry.uuid,
        CommitFilter(repo_branch=repository_registry.branches[0]),
    )

    unit_service.update(
        pytest.units[0].uuid,
        UnitUpdate(
            is_auto_update_from_repo_unit=False,
            repo_branch=repository_registry.branches[0],
            repo_commit=commits[0].commit,
        ),
    )

    # check set auto update
    unit_service.update(
        pytest.units[0].uuid, UnitUpdate(is_auto_update_from_repo_unit=True)
    )

    # check update not creator
    current_user = pytest.users[1]
    unit_service = get_unit_service(
        database, cc, pytest.user_tokens_dict[current_user.uuid]
    )

    with pytest.raises(NoAccessError):
        unit_service.update(
            pytest.units[0].uuid, UnitUpdate(is_auto_update_from_repo_unit=True)
        )


@pytest.mark.run(order=3)
def test_env_unit(database, cc) -> None:
    current_user = pytest.users[0]
    unit_service = get_unit_service(
        database, cc, pytest.user_tokens_dict[current_user.uuid]
    )

    target_unit = pytest.units[0]

    # check count unique variables
    count = len(unit_service.get_env(target_unit.uuid).keys())
    logging.info(f"{count}")
    assert count > 0

    # check set invalid variable
    unit_service.set_env(target_unit.uuid, json.dumps({"test": ""}))

    current_env = unit_service.get_env(target_unit.uuid)
    assert 'test' not in current_env.keys()

    # set valid env variable for Units
    for unit in pytest.units:
        logging.info(unit.uuid)
        current_env = unit_service.get_env(unit.uuid)

        count_before = len(current_env.keys())
        unit_service.set_env(unit.uuid, json.dumps(current_env))
        count_after = len(unit_service.get_env(unit.uuid).keys())

        assert count_before <= count_after

    # test reset_env to default
    test_unit = pytest.units[0]
    current_env = unit_service.get_env(test_unit.uuid)
    old_env = copy.deepcopy(current_env)

    unit_service.reset_env(test_unit.uuid)

    unit_service.set_env(test_unit.uuid, json.dumps(unit_service.get_env(test_unit.uuid)))
    new_env = unit_service.get_env(test_unit.uuid)

    assert old_env.get(ReservedEnvVariableName.SYNC_ENCRYPT_KEY.value) != new_env.get(ReservedEnvVariableName.SYNC_ENCRYPT_KEY.value)


@pytest.mark.run(order=4)
def test_get_firmware(database, cc) -> None:
    current_user = pytest.users[0]
    unit_service = get_unit_service(
        database, cc, pytest.user_tokens_dict[current_user.uuid]
    )

    test_unit_path = "tmp/test_units"

    try:
        os.mkdir(test_unit_path)
    except Exception:
        pass

    methods_list = [
        unit_service.get_unit_firmware_zip,
        unit_service.get_unit_firmware_tar,
        unit_service.get_unit_firmware_tgz,
    ]

    # check create physical unit for all pytest unit - zip, tar, tgz
    del_file_list = []
    for inc, unit in enumerate(pytest.units):
        logging.info(unit.uuid)

        inc = inc % 3

        if inc == 2:
            # tgz
            tgz_path = methods_list[inc](unit.uuid, 9, 9)
            del_file_list.append(tgz_path)

            # make tar
            with open(tgz_path, "rb") as f:
                producer = zlib.decompressobj(wbits=9)
                tar_data = producer.decompress(f.read()) + producer.flush()

                archive_path = f"tmp/{unit.uuid}.tar"
                with open(archive_path, "wb") as tar_file:
                    tar_file.write(tar_data)
        else:
            # zip, tar
            archive_path = methods_list[inc](unit.uuid)

        del_file_list.append(archive_path)

        unpack_path = f"{test_unit_path}/{unit.uuid}"
        shutil.unpack_archive(archive_path, unpack_path, "zip" if inc == 0 else "tar")

        # check env.json file
        with open(f"{unpack_path}/{StaticRepoFileName.ENV.value}", "r") as f:
            env_dict = json.loads(f.read())
            assert len(env_dict["PEPEUNIT_TOKEN"]) > 100

    for item in del_file_list:
        os.remove(item)

    # check gen firmware with bad wbits
    with pytest.raises(UnitError):
        unit_service.get_unit_firmware_tgz(unit.uuid, 35, 9)

    # check gen firmware with bad level
    with pytest.raises(UnitError):
        unit_service.get_unit_firmware_tgz(unit.uuid, 9, 13)

    # check get target commit version
    target_version = unit_service.get_target_version(unit.uuid)
    assert target_version.commit != ""


@pytest.mark.run(order=5)
def test_state_storage(database, cc) -> None:
    current_user = pytest.users[0]
    unit_service = get_unit_service(
        database, cc, pytest.user_tokens_dict[current_user.uuid]
    )

    target_unit = pytest.units[0]

    # check decode encode storage
    state = "test"
    unit_service.set_state_storage(target_unit.uuid, state)
    db_state = unit_service.get_state_storage(target_unit.uuid)
    assert state == db_state

    # check cipher long data
    with pytest.raises(CipherError):
        state = "t" * (settings.backend_max_cipher_length + 1)
        unit_service.set_state_storage(target_unit.uuid, state)


@pytest.mark.run(order=6)
def test_run_infrastructure_contour(database, client_emulator) -> None:
    # run all units
    client_emulator.task_queue.put(pytest.units)


@pytest.mark.run(order=7)
def test_hand_update_firmware_unit(database, client_emulator, cc) -> None:
    current_user = pytest.users[0]
    token = pytest.user_tokens_dict[current_user.uuid]
    logging.info(f"User token: {token}")

    unit_service = get_unit_service(database, cc, token)
    repo_service = get_repo_service(database, cc, token)
    repository_registry_service = get_repository_registry_service(database, token)

    target_units = pytest.units[1:]

    # wait run external Unit
    inc = 0
    while True:
        data = [
            unit_service.get(unit.uuid).current_commit_version for unit in target_units
        ]
        logging.info(data)

        if None not in data:
            break

        time.sleep(1)

        if inc > 10:
            assert False

        inc += 1

    def set_unit_new_commit(token: str, unit, target_version: str) -> int:
        headers = {"accept": "application/json", "x-auth-token": token}

        url = f"{settings.backend_link_prefix_and_v1}/units/{unit.uuid}"

        # send over http, in tests not work mqtt pub and sub
        r = httpx.patch(
            url=url, json=UnitUpdate(repo_commit=target_version).dict(), headers=headers
        )

        return r.status_code

    # set all hand updated unit, old version
    target_versions = []
    for unit in target_units:
        logging.info(unit.uuid)

        repo = repo_service.get(unit.repo_uuid)
        repository_registry = (
            repository_registry_service.mapper_registry_to_registry_read(
                repository_registry_service.get(repo.repository_registry_uuid)
            )
        )
        commits = repository_registry_service.get_branch_commits(
            repository_registry.uuid,
            CommitFilter(
                repo_branch=repository_registry.branches[0],
                only_tag=repo.is_only_tag_update,
            ),
        )
        target_version = commits[1].commit
        target_versions.append(target_version)

        logging.info(f"{unit.name}, {unit.uuid},{target_version}")
        assert set_unit_new_commit(token, unit, target_version) < 400

    logging.info(target_versions[0])

    # wait update to old version external Unit
    inc = 0
    while True:
        data = [
            unit_service.get(unit.uuid).current_commit_version for unit in target_units
        ]
        logging.info(data)

        if data.count(target_versions[0]) == len(target_units):
            break

        time.sleep(1)

        if inc > 10:
            assert False

        inc += 1

    # check update to bad commit
    target_unit = pytest.units[5]
    assert set_unit_new_commit(token, target_unit, "test") >= 400

    # check update to commit with bad env_example.json
    assert (
        set_unit_new_commit(
            token, target_unit, "6506d44fd80a895a57f2b34055521405d0f22860"
        )
        >= 400
    )

    # set bad env
    target_unit = pytest.units[1]
    env_dict = unit_service.get_env(target_unit.uuid)
    del env_dict["SYNC_ENCRYPT_KEY"]

    logging.info(env_dict)

    update_unit = unit_service.get(target_unit.uuid)
    update_unit.cipher_env_dict = aes_gcm_encode(json.dumps(env_dict))

    unit_service.unit_repository.update(target_unit.uuid, update_unit)

    # check update with bad env
    repo = repo_service.get(target_unit.repo_uuid)
    repository_registry = repository_registry_service.mapper_registry_to_registry_read(
        repository_registry_service.get(repo.repository_registry_uuid)
    )
    commits = repository_registry_service.get_branch_commits(
        repository_registry.uuid,
        CommitFilter(repo_branch=repository_registry.branches[0]),
    )
    target_version = commits[0].commit

    assert set_unit_new_commit(token, target_unit, target_version) == 200


@pytest.mark.run(order=8)
def test_repo_update_firmware_unit(database, cc) -> None:
    def set_repo_new_commit(token: str, repo, repo_update: RepoUpdate) -> int:
        headers = {"accept": "application/json", "x-auth-token": token}

        url = f"{settings.backend_link_prefix_and_v1}/repos/{repo.uuid}"

        # send over http, in tests not work mqtt pub and sub
        r = httpx.patch(url=url, json=repo_update.dict(), headers=headers)

        return r.status_code

    def bulk_update_repo(token: str) -> int:
        headers = {"accept": "application/json", "x-auth-token": token}

        url = f"{settings.backend_link_prefix_and_v1}/repos/bulk_update"

        # send over http, in tests not work mqtt pub and sub
        r = httpx.post(url=url, headers=headers)

        return r.status_code

    current_user = pytest.users[0]
    token = pytest.user_tokens_dict[current_user.uuid]
    logging.info(f"User token: {token}")

    unit_service = get_unit_service(database, cc, token)
    repo_service = get_repo_service(database, cc, token)
    repository_registry_service = get_repository_registry_service(database, token)

    target_units = pytest.units[-4:-1]

    # set auto update
    for unit in target_units:
        logging.info(unit.uuid)
        unit_service.update(unit.uuid, UnitUpdate(is_auto_update_from_repo_unit=True))

    # hand update repo
    target_repo = repo_service.get(target_units[0].repo_uuid)
    repository_registry = repository_registry_service.mapper_registry_to_registry_read(
        repository_registry_service.get(target_repo.repository_registry_uuid)
    )
    commits = repository_registry_service.get_branch_commits(
        repository_registry.uuid,
        CommitFilter(repo_branch=repository_registry.branches[0]),
    )
    target_version = commits[0].commit
    assert (
        set_repo_new_commit(
            token, target_repo, RepoUpdate(default_commit=target_version)
        )
        < 400
    )

    # wait hand update unit
    inc = 0
    while True:
        data = unit_service.get(target_units[0].uuid).current_commit_version

        if data == target_version:
            break

        time.sleep(1)

        if inc > 10:
            assert False

        inc += 1

    # auto update repo
    current_user = pytest.users[1]
    assert bulk_update_repo(pytest.user_tokens_dict[current_user.uuid]) < 400

    # wait bulk update unit
    target_repo = repo_service.get(target_units[0].repo_uuid)

    repository_registry = repository_registry_service.mapper_registry_to_registry_read(
        repository_registry_service.get(target_repo.repository_registry_uuid)
    )

    commits = repo_service.git_repo_repository.get_branch_commits_with_tag(
        repository_registry, target_repo.default_branch
    )
    tags = repo_service.git_repo_repository.get_tags_from_all_commits(commits)

    inc = 0
    while True:
        data = [
            unit_service.get(unit.uuid).current_commit_version
            for unit in target_units[-2:]
        ]

        logging.info(data)
        logging.info(tags[0]["commit"])
        logging.info(target_version)

        if data[0] == target_version and data[1] == tags[0]["commit"]:
            break

        time.sleep(2)

        if inc > 10:
            assert False

        inc += 1


@pytest.mark.run(order=9)
def test_env_update_command(database, cc) -> None:
    def set_command(token: str, unit, command: BackendTopicCommand) -> int:
        headers = {"accept": "application/json", "x-auth-token": token}

        url = f"{settings.backend_link_prefix_and_v1}/units/send_command_to_input_base_topic/{unit.uuid}?command={command.value}"

        # send over http, in tests not work mqtt pub and sub
        r = httpx.post(url=url, headers=headers)

        return r.status_code

    current_user = pytest.users[0]
    token = pytest.user_tokens_dict[current_user.uuid]
    unit_service = get_unit_service(
        database, cc, pytest.user_tokens_dict[current_user.uuid]
    )

    target_unit = pytest.units[-2]
    logging.info(target_unit.uuid)

    # set new variable for unit
    current_env = unit_service.get_env(target_unit.uuid)
    current_env["MIN_LOG_LEVEL"] = "Info"
    unit_service.set_env(target_unit.uuid, json.dumps(current_env))

    # send command update env on unit
    assert set_command(token, target_unit, BackendTopicCommand.ENV_UPDATE) < 400

    # check unit emulation save new env.json to file
    inc = 0
    filepath = f"tmp/test_units/{target_unit.uuid}/env.json"
    while True:
        with open(filepath, "r") as f:
            env_dict = json.loads(f.read())

            if env_dict["MIN_LOG_LEVEL"] == "Info":
                break

        time.sleep(2)

        if inc > 10:
            assert False

        inc += 1


@pytest.mark.run(order=10)
def test_log_sync_command(database) -> None:
    def set_command(token: str, unit, command: BackendTopicCommand) -> int:
        headers = {"accept": "application/json", "x-auth-token": token}

        url = f"{settings.backend_link_prefix_and_v1}/units/send_command_to_input_base_topic/{unit.uuid}?command={command.value}"

        # send over http, in tests not work mqtt pub and sub
        r = httpx.post(url=url, headers=headers)

        return r.status_code

    current_user = pytest.users[0]
    token = pytest.user_tokens_dict[current_user.uuid]

    client = next(get_clickhouse_client())
    try:
        unit_log_repository = UnitLogRepository(client)

        target_unit = pytest.units[-3]
        logging.info(target_unit.uuid)

        # send command log sync on unit
        assert set_command(token, target_unit, BackendTopicCommand.LOG_SYNC) < 400

        # check log in clickhouse with level < default - Warning
        inc = 0
        while True:
            count, logs = unit_log_repository.list(
                UnitLogFilter(uuid=target_unit.uuid, level=["Info"])
            )

            logging.info(count)

            if count:
                break

            time.sleep(2)

            if inc > 10:
                assert False

            inc += 1
    finally:
        client.disconnect()


@pytest.mark.run(order=11)
def test_get_many_unit(database, cc) -> None:
    current_user = pytest.users[0]
    unit_service = get_unit_service(
        database, cc, pytest.user_tokens_dict[current_user.uuid]
    )

    # check many get with all filters
    count, units = unit_service.list(
        UnitFilter(
            creator_uuid=current_user.uuid,
            repo_uuid=pytest.repos[-2].uuid,
            search_string=pytest.test_hash,
            is_auto_update_from_repo_unit=True,
            offset=0,
            limit=settings.backend_max_pagination_size,
        )
    )
    assert len(units) == 2


@pytest.mark.run(order=12)
def test_get_unit_logs(database, cc) -> None:
    current_user = pytest.users[0]
    unit_service = get_unit_service(
        database, cc, pytest.user_tokens_dict[current_user.uuid]
    )

    target_unit = pytest.units[-3]

    # check many get with all filters
    count, units = unit_service.log_list(
        UnitLogFilter(
            uuid=target_unit.uuid,
            offset=0,
            limit=settings.backend_max_pagination_size,
        )
    )
    assert len(units) > 0


@pytest.mark.run(order=13)
@pytest.mark.asyncio
async def test_convert_toml_file_to_md(database, cc) -> None:
    current_user = pytest.users[0]
    unit_service = get_unit_service(
        database, cc, pytest.user_tokens_dict[current_user.uuid]
    )

    class DummyUploadFile:
        def __init__(self, content: bytes):
            self._content = content

        async def read(self):
            return self._content

    tests_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    toml_path = os.path.join(tests_dir, "data", "toml", "pepeunit.toml")

    with open(toml_path, "rb") as f:
        content = f.read()

    file = DummyUploadFile(content)

    md = await unit_service.convert_toml_file_to_md(file)

    assert isinstance(md, str)
    assert md.strip() != ""
    assert md.lstrip().startswith("# WiFi Temp Sensor ds18b20")
    assert "Parameter | Implementation" in md
    assert "## Files" in md
