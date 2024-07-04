import asyncio
import json
import os
import shutil
import time
import zlib

import fastapi
import httpx
import pytest
from aiohttp.test_utils import TestClient

from app.configs.gql import get_unit_service, get_repo_service
from app.domain.repo_model import Repo
from app.main import app
from app.repositories.enum import VisibilityLevel
from app.schemas.pydantic.repo import RepoUpdate, CommitFilter
from app.schemas.pydantic.unit import UnitCreate, UnitUpdate
from tests.integration.conftest import Info
from tests.integration.services.utils import check_screen_session_by_name, run_bash_script_on_screen_session


@pytest.mark.run(order=0)
def test_create_unit(database) -> None:

    current_user = pytest.users[0]
    unit_service = get_unit_service(Info({'db': database, 'jwt_token': pytest.user_tokens_dict[current_user.uuid]}))

    # todo refactor перенести в conftest, основные виды unit, добавить некоторым нужные версии и ветки

    # create auto updated units, with all visibility levels
    new_units = []
    for inc, test_repo in enumerate(pytest.repos[-3:]):
        unit = unit_service.create(
            UnitCreate(
                repo_uuid=test_repo.uuid,
                visibility_level=test_repo.visibility_level,
                name=f'test_{inc}_{pytest.test_hash}',
                is_auto_update_from_repo_unit=True,
            )
        )
        new_units.append(unit)

    pytest.units = new_units

    # todo все варианты обновления вместе со всеми вариантами обновления repo

    # check create unit with exist name
    with pytest.raises(fastapi.HTTPException):

        test_repo = pytest.repos[-1]

        unit_service.create(
            UnitCreate(
                repo_uuid=test_repo.uuid,
                visibility_level=test_repo.visibility_level,
                name=f'test_0_{pytest.test_hash}',
                is_auto_update_from_repo_unit=True,
            )
        )

    # check create Unit with Repo without default branch
    repo_service = get_repo_service(Info({'db': database, 'jwt_token': pytest.user_tokens_dict[current_user.uuid]}))
    repo_service.repo_repository.update(pytest.repos[0].uuid, Repo(default_branch=None))

    with pytest.raises(fastapi.HTTPException):
        test_repo = pytest.repos[0]

        unit_service.create(
            UnitCreate(
                repo_uuid=test_repo.uuid,
                visibility_level=test_repo.visibility_level,
                name=f'test_a_{pytest.test_hash}',
                is_auto_update_from_repo_unit=True,
            )
        )

    # check create without env_example and schema.json
    with pytest.raises(fastapi.HTTPException):
        test_repo = pytest.repos[1]

        unit_service.create(
            UnitCreate(
                repo_uuid=test_repo.uuid,
                visibility_level=test_repo.visibility_level,
                name=f'test_b_{pytest.test_hash}',
                is_auto_update_from_repo_unit=True,
            )
        )


@pytest.mark.run(order=1)
def test_update_unit(database) -> None:

    current_user = pytest.users[0]
    unit_service = get_unit_service(Info({'db': database, 'jwt_token': pytest.user_tokens_dict[current_user.uuid]}))

    # check change name to new
    test_unit = pytest.units[0]
    test_unit_name = test_unit.name + 'test'
    unit_service.update(str(test_unit.uuid), UnitUpdate(name=test_unit_name))

    update_unit = unit_service.get(test_unit.uuid)

    assert test_unit_name == update_unit.name

    # change name to normal
    unit_service.update(str(test_unit.uuid), UnitUpdate(name=test_unit.name))

    # check change name when name is exist
    with pytest.raises(fastapi.HTTPException):
        unit_service.update(str(pytest.units[0].uuid), UnitUpdate(name=pytest.units[1].name))

    # check change visibility
    target_unit = pytest.units[0]

    unit_service.update(str(target_unit.uuid), UnitUpdate(visibility_level=VisibilityLevel.INTERNAL))
    update_unit = unit_service.get(target_unit.uuid)
    assert update_unit.visibility_level == VisibilityLevel.INTERNAL

    unit_service.update(str(target_unit.uuid), UnitUpdate(visibility_level=VisibilityLevel.PUBLIC))
    update_unit = unit_service.get(target_unit.uuid)
    assert update_unit.visibility_level == VisibilityLevel.PUBLIC

    # check set not auto update without commit and branch
    with pytest.raises(fastapi.HTTPException):
        unit_service.update(str(pytest.units[0].uuid), UnitUpdate(is_auto_update_from_repo_unit=False))

    # check set hand update
    repo_service = get_repo_service(Info({'db': database, 'jwt_token': pytest.user_tokens_dict[current_user.uuid]}))

    target_unit = pytest.units[0]
    target_repo = repo_service.get(target_unit.repo_uuid)
    commits = repo_service.get_branch_commits(target_repo.uuid, CommitFilter(repo_branch=target_repo.branches[0]))

    unit_service.update(
        str(pytest.units[0].uuid),
        UnitUpdate(
            is_auto_update_from_repo_unit=False, repo_branch=target_repo.branches[0], repo_commit=commits[0].commit
        ),
    )

    # check set auto update
    unit_service.update(str(pytest.units[0].uuid), UnitUpdate(is_auto_update_from_repo_unit=True))

    # check update not creator
    current_user = pytest.users[1]
    unit_service = get_unit_service(Info({'db': database, 'jwt_token': pytest.user_tokens_dict[current_user.uuid]}))

    with pytest.raises(fastapi.HTTPException):
        unit_service.update(str(pytest.units[0].uuid), UnitUpdate(is_auto_update_from_repo_unit=True))


@pytest.mark.run(order=2)
def test_env_unit(database) -> None:

    current_user = pytest.users[0]
    unit_service = get_unit_service(Info({'db': database, 'jwt_token': pytest.user_tokens_dict[current_user.uuid]}))

    target_unit = pytest.units[0]

    # check count unique variables
    assert len(unit_service.get_env(target_unit.uuid).keys()) > 0

    # check set invalid variable
    with pytest.raises(fastapi.HTTPException):
        unit_service.set_env(target_unit.uuid, json.dumps({'test': ''}))

    # set valid env variable for Units
    for unit in pytest.units:
        current_env = unit_service.get_env(unit.uuid)

        count_before = len(current_env.keys())
        unit_service.set_env(unit.uuid, json.dumps(current_env))
        count_after = len(unit_service.get_env(unit.uuid).keys())

        assert count_before < count_after


@pytest.mark.run(order=3)
def test_get_firmware(database) -> None:

    current_user = pytest.users[0]
    unit_service = get_unit_service(Info({'db': database, 'jwt_token': pytest.user_tokens_dict[current_user.uuid]}))

    test_unit_path = 'tmp/test_units'

    try:
        os.mkdir(test_unit_path)
    except:
        pass

    methods_list = [
        unit_service.get_unit_firmware_zip,
        unit_service.get_unit_firmware_tar,
        unit_service.get_unit_firmware_tgz,
    ]

    # check create physical unit for all pytest unit - zip, tar, tgz
    del_file_list = []
    for inc, unit in enumerate(pytest.units[:3]):

        if inc == 2:
            # tgz
            tgz_path = methods_list[inc](unit.uuid, 9, 9)
            del_file_list.append(tgz_path)

            # make tar
            with open(tgz_path, 'rb') as f:
                producer = zlib.decompressobj(wbits=9)
                tar_data = producer.decompress(f.read()) + producer.flush()

                archive_path = f'tmp/{unit.uuid}.tar'
                with open(archive_path, 'wb') as tar_file:
                    tar_file.write(tar_data)
        else:
            # zip, tar
            archive_path = methods_list[inc](unit.uuid)

        del_file_list.append(archive_path)

        unpack_path = f'{test_unit_path}/{unit.uuid}'
        shutil.unpack_archive(archive_path, unpack_path, 'zip' if inc == 0 else 'tar')

        # check env.json file
        with open(f'{unpack_path}/env.json', 'r') as f:
            env_dict = json.loads(f.read())
            assert len(env_dict['PEPEUNIT_TOKEN']) > 100

    for item in del_file_list:
        os.remove(item)

    # check gen firmware with bad wbits
    with pytest.raises(fastapi.HTTPException):
        unit_service.get_unit_firmware_tgz(unit.uuid, 35, 9)

    # check gen firmware with bad level
    with pytest.raises(fastapi.HTTPException):
        unit_service.get_unit_firmware_tgz(unit.uuid, 9, 13)


@pytest.mark.run(order=4)
def test_run_infrastructure_contour() -> None:

    backend_screen_name = 'pepeunit_backend'
    backend_run_script = 'bash tests/entrypoint.sh'

    # run backend
    if not check_screen_session_by_name(backend_screen_name):
        assert run_bash_script_on_screen_session(backend_screen_name, backend_run_script) == True

    # waiting condition backend
    code = 502
    while code >= 500:
        r = httpx.get('https://pepeunit.pepemoss.com/pepeunit')
        code = r.status_code

        time.sleep(2)

    # run units in screen
    for inc, unit in enumerate(pytest.units[:3]):

        unit_screen_name = unit.name
        unit_script = f'cd tmp/test_units/{str(unit.uuid)} && bash entrypoint.sh'

        if not check_screen_session_by_name(unit_screen_name):
            assert run_bash_script_on_screen_session(unit_screen_name, unit_script) == True
