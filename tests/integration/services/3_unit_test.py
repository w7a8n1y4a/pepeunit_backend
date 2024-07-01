import asyncio
import json

import fastapi
import pytest
from aiohttp.test_utils import TestClient

from app.configs.gql import get_unit_service, get_repo_service
from app.domain.repo_model import Repo
from app.main import app
from app.repositories.enum import VisibilityLevel
from app.schemas.pydantic.repo import RepoUpdate, CommitFilter
from app.schemas.pydantic.unit import UnitCreate, UnitUpdate
from tests.integration.conftest import Info


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
