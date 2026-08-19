import copy
import json
import logging
import os

import pytest

from app import settings
from app.configs.clickhouse import get_clickhouse_client
from app.configs.errors import (
    CipherError,
    GitRepoError,
    NoAccessError,
    ReadmeGenerationError,
    UnitError,
    ValidationError,
)
from app.domain.repo_model import Repo
from app.dto.enum import BackendTopicCommand, ReservedEnvVariableName, VisibilityLevel
from app.repositories.unit_log_repository import UnitLogRepository
from app.schemas.pydantic.repo import RepoUpdate
from app.schemas.pydantic.unit import UnitCreate, UnitFilter, UnitLogFilter, UnitUpdate
from app.utils.utils import aes_gcm_encode
from tests.integration.helpers.http import (
    patch_repo,
    patch_unit_commit,
    post_bulk_update_repo,
    post_unit_command,
)
from tests.integration.helpers.names import unique_name
from tests.integration.helpers.services import (
    branch_commits,
    repo_service,
    unit_service,
)
from tests.integration.helpers.wait import wait_until


def test_create_unit(live_units) -> None:
    assert len(live_units.all()) == 9


def test_create_unit_duplicate_name(
    live_units, universal_compile_repo, regular_user_token, database, cc
) -> None:
    service = unit_service(database, cc, regular_user_token)
    with pytest.raises(UnitError):
        service.create(
            UnitCreate(
                repo_uuid=universal_compile_repo.uuid,
                visibility_level=universal_compile_repo.visibility_level,
                name=live_units.universal_auto_unit.name,
                is_auto_update_from_repo_unit=True,
            )
        )


def test_create_unit_without_default_branch(
    crud_repo, regular_user_token, database, cc
) -> None:
    service = unit_service(database, cc, regular_user_token)
    repo_svc = repo_service(database, cc, regular_user_token)
    target_repo = Repo(**crud_repo.__dict__)
    target_repo.default_branch = None
    repo_svc.repo_repository.update(crud_repo.uuid, target_repo)

    with pytest.raises(GitRepoError):
        service.create(
            UnitCreate(
                repo_uuid=crud_repo.uuid,
                visibility_level=crud_repo.visibility_level,
                name=unique_name("nobr"),
                is_auto_update_from_repo_unit=True,
            )
        )


def test_delete_repo_with_unit(
    universal_compile_repo, compile_unit, regular_user_token, database, cc
) -> None:
    repo_svc = repo_service(database, cc, regular_user_token)
    with pytest.raises(ValidationError):
        repo_svc.delete(universal_compile_repo.uuid)


def test_update_unit_name(
    crud_unit, regular_user_token, database, cc
) -> None:
    service = unit_service(database, cc, regular_user_token)
    original = crud_unit.name
    new_name = unique_name("unm")
    service.update(crud_unit.uuid, UnitUpdate(name=new_name))
    assert service.get(crud_unit.uuid).name == new_name
    service.update(crud_unit.uuid, UnitUpdate(name=original))


def test_update_unit_name_exists(
    live_units, regular_user_token, database, cc
) -> None:
    service = unit_service(database, cc, regular_user_token)
    with pytest.raises(UnitError):
        service.update(
            live_units.universal_auto_unit.uuid,
            UnitUpdate(name=live_units.universal_manual_unit.name),
        )


def test_update_unit_visibility(
    universal_manual_unit, regular_user_token, database, cc
) -> None:
    service = unit_service(database, cc, regular_user_token)
    logging.info(universal_manual_unit.uuid)

    service.update(
        universal_manual_unit.uuid, UnitUpdate(visibility_level=VisibilityLevel.INTERNAL)
    )
    assert service.get(universal_manual_unit.uuid).visibility_level == VisibilityLevel.INTERNAL

    service.update(
        universal_manual_unit.uuid, UnitUpdate(visibility_level=VisibilityLevel.PUBLIC)
    )
    assert service.get(universal_manual_unit.uuid).visibility_level == VisibilityLevel.PUBLIC


def test_update_unit_auto_flags(
    universal_auto_unit, regular_user_token, database, cc
) -> None:
    service = unit_service(database, cc, regular_user_token)
    with pytest.raises(UnitError):
        service.update(
            universal_auto_unit.uuid, UnitUpdate(is_auto_update_from_repo_unit=False)
        )

    repo_svc = repo_service(database, cc, regular_user_token)
    target_repo = repo_svc.get(universal_auto_unit.repo_uuid)
    read, commits = branch_commits(
        database, regular_user_token, target_repo.repository_registry_uuid
    )
    service.update(
        universal_auto_unit.uuid,
        UnitUpdate(
            is_auto_update_from_repo_unit=False,
            repo_branch=read.branches[0],
            repo_commit=commits[0].commit,
        ),
    )
    service.update(
        universal_auto_unit.uuid, UnitUpdate(is_auto_update_from_repo_unit=True)
    )


def test_update_unit_not_creator(
    universal_auto_unit, admin_user_token, database, cc
) -> None:
    service = unit_service(database, cc, admin_user_token)
    with pytest.raises(NoAccessError):
        service.update(
            universal_auto_unit.uuid, UnitUpdate(is_auto_update_from_repo_unit=True)
        )


def test_env_unit(universal_auto_unit, live_units, regular_user_token, database, cc) -> None:
    service = unit_service(database, cc, regular_user_token)
    count = len(service.get_env(universal_auto_unit.uuid).keys())
    logging.info(f"{count}")
    assert count > 0

    service.set_env(universal_auto_unit.uuid, json.dumps({"test": ""}))
    current_env = service.get_env(universal_auto_unit.uuid)
    assert "test" not in current_env.keys()

    for unit in live_units.all():
        logging.info(unit.uuid)
        current_env = service.get_env(unit.uuid)
        count_before = len(current_env.keys())
        service.set_env(unit.uuid, json.dumps(current_env))
        count_after = len(service.get_env(unit.uuid).keys())
        assert count_before <= count_after


def test_reset_env(universal_auto_unit, regular_user_token, database, cc) -> None:
    service = unit_service(database, cc, regular_user_token)
    current_env = service.get_env(universal_auto_unit.uuid)
    old_env = copy.deepcopy(current_env)

    service.reset_env(universal_auto_unit.uuid)
    service.set_env(
        universal_auto_unit.uuid, json.dumps(service.get_env(universal_auto_unit.uuid))
    )
    new_env = service.get_env(universal_auto_unit.uuid)
    assert old_env.get(ReservedEnvVariableName.PU_SECRET_KEY.value) != new_env.get(
        ReservedEnvVariableName.PU_SECRET_KEY.value
    )


def test_get_firmware(unpacked_firmwares, compile_unit, regular_user_token, database, cc) -> None:
    service = unit_service(database, cc, regular_user_token)
    with pytest.raises(UnitError):
        service.get_unit_firmware_tgz(compile_unit.uuid, 35, 9)
    with pytest.raises(UnitError):
        service.get_unit_firmware_tgz(compile_unit.uuid, 9, 13)

    target_version = service.get_target_version(compile_unit.uuid)
    assert target_version.commit != ""


def test_state_storage(universal_auto_unit, regular_user_token, database, cc) -> None:
    service = unit_service(database, cc, regular_user_token)
    state = "test"
    service.set_state_storage(universal_auto_unit.uuid, state)
    assert state == service.get_state_storage(universal_auto_unit.uuid)

    with pytest.raises(CipherError):
        service.set_state_storage(
            universal_auto_unit.uuid, "t" * (settings.pu_max_cipher_length + 1)
        )


def test_run_infrastructure_contour(running_units) -> None:
    assert len(running_units.all()) == 9


def test_hand_update_firmware_unit(
    running_units, regular_user_token, database, cc
) -> None:
    token = regular_user_token
    logging.info(f"User token: {token}")
    service = unit_service(database, cc, token)
    repo_svc = repo_service(database, cc, token)
    target_units = running_units.firmware_manual()

    target_versions = []
    for unit in target_units:
        logging.info(unit.uuid)
        repo = repo_svc.get(unit.repo_uuid)
        read, commits = branch_commits(
            database,
            token,
            repo.repository_registry_uuid,
            only_tag=repo.is_only_tag_update,
        )
        target_version = commits[1].commit
        target_versions.append(target_version)
        logging.info(f"{unit.name}, {unit.uuid},{target_version}")
        assert patch_unit_commit(token, unit, target_version) < 400

    logging.info(target_versions[0])
    wait_until(
        lambda: [
            service.get(unit.uuid).current_commit_version for unit in target_units
        ].count(target_versions[0])
        == len(target_units),
        timeout=30,
        message="hand firmware update did not reach target commit",
        session=database,
    )


def test_hand_update_bad_commit(
    running_units, chain_source_unit, regular_user_token
) -> None:
    assert patch_unit_commit(regular_user_token, chain_source_unit, "test") >= 400
    assert (
        patch_unit_commit(
            regular_user_token,
            chain_source_unit,
            "6506d44fd80a895a57f2b34055521405d0f22860",
        )
        >= 400
    )


def test_hand_update_with_bad_env(
    running_units, universal_manual_unit, regular_user_token, database, cc
) -> None:
    token = regular_user_token
    service = unit_service(database, cc, token)
    repo_svc = repo_service(database, cc, token)

    env_dict = service.get_env(universal_manual_unit.uuid)
    del env_dict["PU_SECRET_KEY"]
    logging.info(env_dict)

    update_unit = service.get(universal_manual_unit.uuid)
    update_unit.cipher_env_dict = aes_gcm_encode(json.dumps(env_dict))
    service.unit_repository.update(universal_manual_unit.uuid, update_unit)

    repo = repo_svc.get(universal_manual_unit.repo_uuid)
    _, commits = branch_commits(database, token, repo.repository_registry_uuid)
    assert patch_unit_commit(token, universal_manual_unit, commits[0].commit) == 200


def test_repo_update_firmware_unit(
    running_units, admin_user_token, regular_user_token, database, cc
) -> None:
    token = regular_user_token
    service = unit_service(database, cc, token)
    repo_svc = repo_service(database, cc, token)
    target_units = running_units.chain()

    for unit in target_units:
        logging.info(unit.uuid)
        service.update(unit.uuid, UnitUpdate(is_auto_update_from_repo_unit=True))

    target_repo = repo_svc.get(target_units[0].repo_uuid)
    _, commits = branch_commits(database, token, target_repo.repository_registry_uuid)
    target_version = commits[0].commit
    assert patch_repo(token, target_repo, RepoUpdate(default_commit=target_version)) < 400

    wait_until(
        lambda: service.get(target_units[0].uuid).current_commit_version == target_version,
        timeout=30,
        message="hand repo update did not reach unit commit",
        session=database,
    )

    assert post_bulk_update_repo(admin_user_token) < 400

    target_repo = repo_svc.get(target_units[0].repo_uuid)
    from tests.integration.helpers.services import registry_service

    registry_svc = registry_service(database, token)
    repository_registry = registry_svc.mapper_registry_to_registry_read(
        registry_svc.get(target_repo.repository_registry_uuid)
    )
    commits_with_tag = repo_svc.git_repo_repository.get_branch_commits_with_tag(
        repository_registry, target_repo.default_branch
    )
    tags = repo_svc.git_repo_repository.get_tags_from_all_commits(commits_with_tag)
    tag_commit = tags[0]["commit"]

    middle = target_units[-2]
    sink = target_units[-1]

    def bulk_reached() -> bool:
        middle_commit = service.get(middle.uuid).current_commit_version
        sink_commit = service.get(sink.uuid).current_commit_version
        logging.info((middle_commit, sink_commit, target_version, tag_commit))
        return middle_commit == target_version and sink_commit == tag_commit

    wait_until(
        bulk_reached,
        timeout=30,
        interval=2,
        message="bulk repo update did not reach chain units",
        session=database,
    )


def test_env_update_command(
    running_units, chain_sink_unit, regular_user_token, database, cc
) -> None:
    token = regular_user_token
    service = unit_service(database, cc, token)
    logging.info(chain_sink_unit.uuid)

    current_env = service.get_env(chain_sink_unit.uuid)
    current_env["PU_MIN_LOG_LEVEL"] = "Info"
    service.set_env(chain_sink_unit.uuid, json.dumps(current_env))

    assert post_unit_command(token, chain_sink_unit, BackendTopicCommand.ENV_UPDATE) < 400

    filepath = f"tmp/test_units/{chain_sink_unit.uuid}/env.json"

    def env_updated() -> bool:
        with open(filepath) as handle:
            return json.loads(handle.read())["PU_MIN_LOG_LEVEL"] == "Info"

    wait_until(
        env_updated,
        timeout=30,
        interval=2,
        message="env.json was not updated on unit",
    )


def test_log_sync_command(running_units, chain_middle_unit, regular_user_token) -> None:
    token = regular_user_token
    client = next(get_clickhouse_client())
    try:
        unit_log_repository = UnitLogRepository(client)
        logging.info(chain_middle_unit.uuid)
        assert post_unit_command(token, chain_middle_unit, BackendTopicCommand.LOG_SYNC) < 400

        wait_until(
            lambda: unit_log_repository.list(
                UnitLogFilter(uuid=chain_middle_unit.uuid, level=["Info"])
            )[0]
            > 0,
            timeout=30,
            interval=2,
            message="LOG_SYNC did not produce Info rows in ClickHouse",
        )
    finally:
        client.disconnect()


def test_get_many_unit(
    live_units,
    universal_auto_unit,
    universal_private_repo,
    regular_user,
    regular_user_token,
    database,
    cc,
    test_hash,
) -> None:
    service = unit_service(database, cc, regular_user_token)
    count, units = service.list(
        UnitFilter(
            creator_uuid=regular_user.uuid,
            repo_uuid=universal_private_repo.uuid,
            search_string=test_hash,
            is_auto_update_from_repo_unit=True,
            offset=0,
            limit=settings.pu_max_pagination_size,
        )
    )
    assert any(unit[0].uuid == universal_auto_unit.uuid for unit in units)
    assert len(units) >= 1


def test_get_unit_logs(
    running_units, chain_middle_unit, regular_user_token, database, cc
) -> None:
    service = unit_service(database, cc, regular_user_token)
    count, logs = service.log_list(
        UnitLogFilter(
            uuid=chain_middle_unit.uuid,
            offset=0,
            limit=settings.pu_max_pagination_size,
        )
    )
    assert len(logs) > 0


@pytest.mark.asyncio
async def test_convert_toml_file_to_md(regular_user_token, database, cc) -> None:
    service = unit_service(database, cc, regular_user_token)

    class DummyUploadFile:
        def __init__(self, content: bytes):
            self._content = content

        async def read(self):
            return self._content

    tests_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    base_toml_dir = os.path.join(tests_dir, "data", "toml")

    toml_path = os.path.join(base_toml_dir, "pepeunit.toml")
    with open(toml_path, "rb") as handle:
        content = handle.read()
    md = await service.convert_toml_file_to_md(DummyUploadFile(content))
    assert isinstance(md, str)
    assert md.strip() != ""
    assert md.lstrip().startswith("# WiFi Temp Sensor ds18b20")
    assert "Parameter | Implementation" in md
    assert "## Files" in md

    bad_files = [
        "bad_size_pepeunit.toml",
        "bad_syntax_pepeunit.toml",
        "bad_general_items_pepeunit.toml",
        "bad_general_text_pepeunit.toml",
    ]
    for bad_name in bad_files:
        with open(os.path.join(base_toml_dir, bad_name), "rb") as handle:
            bad_content = handle.read()
        with pytest.raises(ReadmeGenerationError):
            await service.convert_toml_file_to_md(DummyUploadFile(bad_content))
