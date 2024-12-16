import hashlib
import json
import shutil
from json import JSONDecodeError

import pytest
from sqlmodel import Session

from app import settings
from app.configs.db import get_session
from app.domain.repo_model import Repo
from app.domain.unit_model import Unit
from app.domain.unit_node_model import UnitNode
from app.domain.user_model import User
from app.repositories.enum import VisibilityLevel
from app.schemas.pydantic.repo import Credentials
from tests.integration.services.utils import check_screen_session_by_name, kill_screen_session

test_hash = hashlib.md5(settings.backend_domain.encode('utf-8')).hexdigest()[:5]


def pytest_configure():
    # search hash for db
    pytest.test_hash = test_hash

    # last - Admin, first - User: minimal 2 users
    pytest.users = []

    # {uuid_user: jwt-token}: minimal 2 items
    pytest.user_tokens_dict = {}

    # ['Private', 'Private', 'Public', 'Public', 'Public', 'Internal', 'Private'] : minimal 7 repo
    pytest.repos = []

    # ['update check', ' bad env.json', 'hand public', 'hand internal', 'hand private', 'auto ', 'auto', 'auto']
    pytest.units = []

    # only for one unit
    pytest.edges = []

    # only save
    pytest.permissions = []


@pytest.fixture(scope="session")
def database() -> Session:
    return next(get_session())


@pytest.fixture
def clear_database(database) -> None:
    """
    clear all entity in database with test_hash in field
    """

    # stop backend in screen
    backend_screen_name = 'pepeunit_backend'
    if check_screen_session_by_name(backend_screen_name):
        kill_screen_session(backend_screen_name)

    # del units
    shutil.rmtree('tmp/test_units', ignore_errors=True)
    shutil.rmtree('tmp/test_units_tar_tgz', ignore_errors=True)

    # clear screen with units
    units = database.query(Unit).where(Unit.name.ilike(f'%{test_hash}%')).all()
    for unit in units:
        if check_screen_session_by_name(unit.name):
            kill_screen_session(unit.name)

    database.query(Unit).where(Unit.name.ilike(f'%{test_hash}%')).delete()

    # clear physical repos
    repos = database.query(Repo).where(Repo.name.ilike(f'%{test_hash}%')).all()
    for repo in repos:
        target_del_path = f'{settings.save_repo_path}/{repo.uuid}'
        try:
            shutil.rmtree(target_del_path)
        except FileNotFoundError:
            pass

    database.query(Repo).where(Repo.uuid.in_([repo.uuid for repo in repos])).delete()
    database.query(User).where(User.login.ilike(f'%{test_hash}%')).delete()
    database.commit()


@pytest.fixture()
def test_users() -> list[dict]:
    return [
        {
            "login": f'test_{inc}_{test_hash}',
            "password": f'testtest{inc}',
        }
        for inc in range(2)
    ]


@pytest.fixture()
def test_repos() -> list[dict]:

    # get private repository
    test_repos = []
    try:
        data = json.loads(settings.test_private_repo_json)
        test_repos.extend(data['data'])
    except JSONDecodeError:
        pass

    # add public repository
    test_repos.extend(
        [
            {
                'type': VisibilityLevel.PUBLIC,
                'is_public': True,
                'link': 'https://git.pepemoss.com/pepe/pepeunit/units/gitlab_unit_pub_test.git',
                'platform': 'Gitlab',
                'compile': True,
            },
            {
                'type': VisibilityLevel.PUBLIC,
                'is_public': True,
                'link': 'https://github.com/w7a8n1y4a/github_unit_pub_test.git',
                'platform': 'Github',
                'compile': True,
            },
            {
                'type': VisibilityLevel.PUBLIC,
                'is_public': True,
                'link': 'https://git.pepemoss.com/pepe/pepeunit/units/universal_test_unit.git',
                'platform': 'Gitlab',
            },
            {
                'type': VisibilityLevel.INTERNAL,
                'is_public': True,
                'link': 'https://git.pepemoss.com/pepe/pepeunit/units/universal_test_unit.git',
                'platform': 'Gitlab',
            },
            {
                'type': VisibilityLevel.PRIVATE,
                'is_public': True,
                'link': 'https://git.pepemoss.com/pepe/pepeunit/units/universal_test_unit.git',
                'platform': 'Gitlab',
            },
            {
                'type': VisibilityLevel.PUBLIC,
                'is_public': True,
                'link': 'https://git.pepemoss.com/pepe/pepeunit/units/universal_test_unit.git',
                'platform': 'Gitlab',
                'compile': True,
            },
        ]
    )

    return [
        {
            'visibility_level': repo['type'],
            'name': f'test_{inc}_{test_hash}',
            'repo_url': repo['link'],
            'is_public_repository': repo['is_public'],
            'platform': repo['platform'],
            'is_compilable_repo': repo['compile'] if 'compile' in repo else False,
            'credentials': (
                None
                if repo['is_public'] == True
                else Credentials(username=repo['username'], pat_token=repo['pat_token'])
            ),
            'is_auto_update_repo': True,
        }
        for inc, repo in enumerate(test_repos)
    ]
