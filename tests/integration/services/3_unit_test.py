import json
import logging
import os
import shutil
import time
import zlib

import fastapi
import httpx
import pytest

from app import settings
from app.configs.gql import get_repo_service, get_unit_service
from app.configs.sub_entities import InfoSubEntity
from app.domain.repo_model import Repo
from app.repositories.enum import StaticRepoFileName, VisibilityLevel
from app.schemas.pydantic.repo import CommitFilter, RepoUpdate
from app.schemas.pydantic.unit import UnitCreate, UnitFilter, UnitUpdate
from app.utils.utils import aes_encode
from tests.integration.services.utils import check_screen_session_by_name, run_bash_script_on_screen_session


@pytest.mark.run(order=0)
def test_create_unit(database) -> None:

    current_user = pytest.users[0]
    unit_service = get_unit_service(
        InfoSubEntity({'db': database, 'jwt_token': pytest.user_tokens_dict[current_user.uuid]})
    )

    # create auto updated unit
    new_units = []
    for inc, test_repo in enumerate(pytest.repos[-2:-1]):
        logging.info(test_repo.uuid)
        unit = unit_service.create(
            UnitCreate(
                repo_uuid=test_repo.uuid,
                visibility_level=test_repo.visibility_level,
                name=f'test_{inc}_{pytest.test_hash}',
                is_auto_update_from_repo_unit=True,
            )
        )
        new_units.append(unit)

    # create no auto updated units, with all visibility levels
    for inc, test_repo in enumerate([pytest.repos[-4]] + pytest.repos[-4:-1] * 2 + [pytest.repos[-1]]):
        logging.info(test_repo.uuid)
        repo_service = get_repo_service(
            InfoSubEntity({'db': database, 'jwt_token': pytest.user_tokens_dict[current_user.uuid]})
        )
        commits = repo_service.get_branch_commits(test_repo.uuid, CommitFilter(repo_branch=test_repo.branches[0]))

        unit = unit_service.create(
            UnitCreate(
                repo_uuid=test_repo.uuid,
                visibility_level=test_repo.visibility_level,
                name=f'test_{inc+1}_{pytest.test_hash}',
                is_auto_update_from_repo_unit=False,
                repo_branch=test_repo.branches[0],
                repo_commit=commits[0].commit,
                target_firmware_platform='Universal' if test_repo.is_compilable_repo else None,
            )
        )
        new_units.append(unit)

    pytest.units = new_units

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
    repo_service = get_repo_service(
        InfoSubEntity({'db': database, 'jwt_token': pytest.user_tokens_dict[current_user.uuid]})
    )
    target_repo = Repo(**pytest.repos[0].__dict__)
    target_repo.default_branch = None
    repo_service.repo_repository.update(pytest.repos[0].uuid, target_repo)

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

    # check create without env_example and schema_example.json
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
def test_delete_repo_with_unit(database) -> None:

    current_user = pytest.users[0]
    repo_service = get_repo_service(
        InfoSubEntity({'db': database, 'jwt_token': pytest.user_tokens_dict[current_user.uuid]})
    )

    # test del repo with Unit
    with pytest.raises(fastapi.HTTPException):
        repo_service.delete(pytest.repos[-1].uuid)


@pytest.mark.run(order=2)
def test_update_unit(database) -> None:

    current_user = pytest.users[0]
    unit_service = get_unit_service(
        InfoSubEntity({'db': database, 'jwt_token': pytest.user_tokens_dict[current_user.uuid]})
    )

    # check change name to new
    test_unit = pytest.units[0]
    test_unit_name = test_unit.name + 'test'
    unit_service.update(test_unit.uuid, UnitUpdate(name=test_unit_name))

    update_unit = unit_service.get(test_unit.uuid)

    assert test_unit_name == update_unit.name

    # change name to normal
    unit_service.update(test_unit.uuid, UnitUpdate(name=test_unit.name))

    # check change name when name is exist
    with pytest.raises(fastapi.HTTPException):
        unit_service.update(pytest.units[0].uuid, UnitUpdate(name=pytest.units[1].name))

    # check change visibility
    target_unit = pytest.units[1]
    logging.info(target_unit.uuid)

    unit_service.update(target_unit.uuid, UnitUpdate(visibility_level=VisibilityLevel.INTERNAL))
    update_unit = unit_service.get(target_unit.uuid)
    assert update_unit.visibility_level == VisibilityLevel.INTERNAL

    unit_service.update(target_unit.uuid, UnitUpdate(visibility_level=VisibilityLevel.PUBLIC))
    update_unit = unit_service.get(target_unit.uuid)
    assert update_unit.visibility_level == VisibilityLevel.PUBLIC

    # check set not auto update without commit and branch
    with pytest.raises(fastapi.HTTPException):
        unit_service.update(pytest.units[0].uuid, UnitUpdate(is_auto_update_from_repo_unit=False))

    # check set hand update
    repo_service = get_repo_service(
        InfoSubEntity({'db': database, 'jwt_token': pytest.user_tokens_dict[current_user.uuid]})
    )

    target_unit = pytest.units[0]
    target_repo = repo_service.get(target_unit.repo_uuid)
    commits = repo_service.get_branch_commits(target_repo.uuid, CommitFilter(repo_branch=target_repo.branches[0]))

    unit_service.update(
        pytest.units[0].uuid,
        UnitUpdate(
            is_auto_update_from_repo_unit=False, repo_branch=target_repo.branches[0], repo_commit=commits[0].commit
        ),
    )

    # check set auto update
    unit_service.update(pytest.units[0].uuid, UnitUpdate(is_auto_update_from_repo_unit=True))

    # check update not creator
    current_user = pytest.users[1]
    unit_service = get_unit_service(
        InfoSubEntity({'db': database, 'jwt_token': pytest.user_tokens_dict[current_user.uuid]})
    )

    with pytest.raises(fastapi.HTTPException):
        unit_service.update(pytest.units[0].uuid, UnitUpdate(is_auto_update_from_repo_unit=True))


@pytest.mark.run(order=3)
def test_env_unit(database) -> None:

    current_user = pytest.users[0]
    unit_service = get_unit_service(
        InfoSubEntity({'db': database, 'jwt_token': pytest.user_tokens_dict[current_user.uuid]})
    )

    target_unit = pytest.units[0]

    # check count unique variables
    count = len(unit_service.get_env(target_unit.uuid).keys())
    logging.info(f'{count}')
    assert count > 0

    # check set invalid variable
    with pytest.raises(fastapi.HTTPException):
        unit_service.set_env(target_unit.uuid, json.dumps({'test': ''}))

    # set valid env variable for Units
    for unit in pytest.units:
        logging.info(unit.uuid)
        current_env = unit_service.get_env(unit.uuid)

        count_before = len(current_env.keys())
        unit_service.set_env(unit.uuid, json.dumps(current_env))
        count_after = len(unit_service.get_env(unit.uuid).keys())

        assert count_before < count_after


@pytest.mark.run(order=4)
def test_get_firmware(database) -> None:

    current_user = pytest.users[0]
    unit_service = get_unit_service(
        InfoSubEntity({'db': database, 'jwt_token': pytest.user_tokens_dict[current_user.uuid]})
    )

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
    for inc, unit in enumerate(pytest.units):
        logging.info(unit.uuid)

        inc = inc % 3

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
        with open(f'{unpack_path}/{StaticRepoFileName.ENV}', 'r') as f:
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


@pytest.mark.run(order=5)
def test_run_infrastructure_contour(database) -> None:

    backend_screen_name = 'pepeunit_backend'
    backend_run_script = 'bash tests/entrypoint.sh'

    # run backend
    if not check_screen_session_by_name(backend_screen_name):
        assert run_bash_script_on_screen_session(backend_screen_name, backend_run_script) == True

    # waiting condition backend
    code = 502
    inc = 0
    while code >= 500 and inc <= 10:
        try:
            r = httpx.get(settings.backend_link_prefix)
            code = r.status_code
        except httpx.ConnectError:
            logging.info('No route to BACKEND_DOMAIN variable')
        except httpx.ConnectTimeout:
            logging.info('Connect timeout to BACKEND_DOMAIN variable')

        if inc > 10:
            assert False

        time.sleep(3)

        inc += 1

    # TODO: придумать как изменить проверку
    time.sleep(10)

    current_user = pytest.users[0]
    token = pytest.user_tokens_dict[current_user.uuid]
    logging.info(f'User token: {token}')

    repo_service = get_repo_service(InfoSubEntity({'db': database, 'jwt_token': token}))

    # run units in screen
    for inc, unit in enumerate(pytest.units):

        logging.info(unit.uuid)

        unit_screen_name = unit.name
        if inc == 8:
            # only for compile

            target_repo = repo_service.repo_repository.get(Repo(uuid=unit.repo_uuid))
            target_version, target_tag = repo_service.git_repo_repository.get_target_unit_version(target_repo, unit)

            links = json.loads(target_repo.releases_data)[target_tag]
            platform, link = repo_service.git_repo_repository.find_by_platform(links, unit.target_firmware_platform)

            unit_script = f'cd tmp/test_units/{unit.uuid} && curl {link} --output test.zip && unzip test.zip -d test && cp -r test/* ./ && bash entrypoint.sh'

        else:
            unit_script = f'cd tmp/test_units/{unit.uuid} && bash entrypoint.sh'

        if not check_screen_session_by_name(unit_screen_name):
            assert run_bash_script_on_screen_session(unit_screen_name, unit_script) == True

        time.sleep(1)


@pytest.mark.run(order=6)
def test_hand_update_firmware_unit(database) -> None:

    current_user = pytest.users[0]
    token = pytest.user_tokens_dict[current_user.uuid]
    logging.info(f'User token: {token}')

    unit_service = get_unit_service(InfoSubEntity({'db': database, 'jwt_token': token}))
    repo_service = get_repo_service(InfoSubEntity({'db': database, 'jwt_token': token}))

    target_units = pytest.units[1:]

    # wait run external Unit
    inc = 0
    while True:

        data = [unit_service.get(unit.uuid).current_commit_version for unit in target_units]
        logging.info(data)

        if None not in data:
            break

        time.sleep(5)

        if inc > 10:
            assert False

        inc += 1

    def set_unit_new_commit(token: str, unit, target_version: str) -> int:
        headers = {'accept': 'application/json', 'x-auth-token': token}

        url = f'{settings.backend_link_prefix_and_v1}/units/{unit.uuid}'

        # send over http, in tests not work mqtt pub and sub
        r = httpx.patch(url=url, json=UnitUpdate(repo_commit=target_version).dict(), headers=headers)

        return r.status_code

    # set all hand updated unit, old version
    target_versions = []
    for unit in target_units:
        logging.info(unit.uuid)

        repo = repo_service.get(unit.repo_uuid)
        commits = repo_service.get_branch_commits(
            repo.uuid, CommitFilter(repo_branch=repo.branches[0], only_tag=repo.is_only_tag_update)
        )
        print(commits)
        target_version = commits[1].commit
        target_versions.append(target_version)

        logging.info(f'{unit.name}, {unit.uuid},{target_version}')
        assert set_unit_new_commit(token, unit, target_version) < 400

    logging.info(target_versions[0])

    # wait update to old version external Unit
    inc = 0
    while True:
        data = [unit_service.get(unit.uuid).current_commit_version for unit in target_units]
        logging.info(data)

        if data.count(target_versions[0]) == len(target_units):
            break

        time.sleep(5)

        if inc > 10:
            assert False

        inc += 1

    # check update to bad commit
    target_unit = pytest.units[5]
    assert set_unit_new_commit(token, target_unit, 'test') >= 400

    # check update to commit with bad env_example.json
    assert set_unit_new_commit(token, target_unit, '6506d44fd80a895a57f2b34055521405d0f22860') >= 400

    # set bad env
    target_unit = pytest.units[1]
    env_dict = unit_service.get_env(target_unit.uuid)
    del env_dict['SYNC_ENCRYPT_KEY']

    logging.info(env_dict)

    update_unit = unit_service.get(target_unit.uuid)
    update_unit.cipher_env_dict = aes_encode(json.dumps(env_dict))

    unit_service.unit_repository.update(target_unit.uuid, update_unit)

    # check update with bad env
    repo = repo_service.get(target_unit.repo_uuid)
    commits = repo_service.get_branch_commits(repo.uuid, CommitFilter(repo_branch=repo.branches[0]))
    target_version = commits[0].commit

    assert set_unit_new_commit(token, target_unit, target_version) == 200


@pytest.mark.run(order=7)
def test_repo_update_firmware_unit(database) -> None:

    def set_repo_new_commit(token: str, repo, repo_update: RepoUpdate) -> int:
        headers = {'accept': 'application/json', 'x-auth-token': token}

        url = f'{settings.backend_link_prefix_and_v1}/repos/{repo.uuid}'

        # send over http, in tests not work mqtt pub and sub
        r = httpx.patch(url=url, json=repo_update.dict(), headers=headers)

        return r.status_code

    def bulk_update_repo(token: str) -> int:
        headers = {'accept': 'application/json', 'x-auth-token': token}

        url = f'{settings.backend_link_prefix_and_v1}/repos/bulk_update'

        # send over http, in tests not work mqtt pub and sub
        r = httpx.post(url=url, headers=headers)

        return r.status_code

    current_user = pytest.users[0]
    token = pytest.user_tokens_dict[current_user.uuid]
    logging.info(f'User token: {token}')

    unit_service = get_unit_service(InfoSubEntity({'db': database, 'jwt_token': token}))
    repo_service = get_repo_service(InfoSubEntity({'db': database, 'jwt_token': token}))

    target_units = pytest.units[-4:-1]

    # set auto update
    for unit in target_units:
        logging.info(unit.uuid)
        unit_service.update(unit.uuid, UnitUpdate(is_auto_update_from_repo_unit=True))

    # hand update repo
    target_repo = repo_service.get(target_units[0].repo_uuid)
    commits = repo_service.get_branch_commits(target_repo.uuid, CommitFilter(repo_branch=target_repo.branches[0]))
    target_version = commits[0].commit
    assert set_repo_new_commit(token, target_repo, RepoUpdate(default_commit=target_version)) < 400

    # wait hand update unit
    inc = 0
    while True:
        data = unit_service.get(target_units[0].uuid).current_commit_version

        if data == target_version:
            break

        time.sleep(5)

        if inc > 10:
            assert False

        inc += 1

    # auto update repo
    current_user = pytest.users[1]
    assert bulk_update_repo(pytest.user_tokens_dict[current_user.uuid]) < 400

    # wait bulk update unit
    target_repo = repo_service.get(target_units[0].repo_uuid)

    commits = repo_service.git_repo_repository.get_branch_commits_with_tag(target_repo, target_repo.default_branch)
    tags = repo_service.git_repo_repository.get_tags_from_all_commits(commits)

    inc = 0
    while True:
        data = [unit_service.get(unit.uuid).current_commit_version for unit in target_units[-2:]]

        logging.info(data)
        logging.info(tags[0]['commit'])
        logging.info(target_version)

        if data[0] == target_version and data[1] == tags[0]['commit']:
            break

        time.sleep(5)

        if inc > 10:
            assert False

        inc += 1


@pytest.mark.run(order=8)
def test_get_many_unit(database) -> None:

    current_user = pytest.users[0]
    unit_service = get_unit_service(
        InfoSubEntity({'db': database, 'jwt_token': pytest.user_tokens_dict[current_user.uuid]})
    )

    # check many get with all filters
    count, units = unit_service.list(
        UnitFilter(
            creator_uuid=current_user.uuid,
            repo_uuid=pytest.repos[-2].uuid,
            search_string=pytest.test_hash,
            is_auto_update_from_repo_unit=True,
            offset=0,
            limit=1_000_000,
        )
    )
    assert len(units) == 2
