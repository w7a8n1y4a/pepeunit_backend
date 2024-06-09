from collections import namedtuple
import hashlib

import pytest

from app import settings
from app.configs.db import get_session
from app.domain.repo_model import Repo
from app.domain.unit_model import Unit
from app.domain.unit_node_model import UnitNode
from app.domain.user_model import User
from sqlmodel import Session

test_hash = hashlib.md5(settings.backend_domain.encode('utf-8')).hexdigest()

Info = namedtuple('Info', "context")


def pytest_configure():
    pytest.users = []
    pytest.user_tokens_dict = {}


@pytest.fixture(scope="session")
def database() -> Session:
    return next(get_session())


@pytest.fixture
def clear_database(database) -> None:
    """
    clear all entity in database with test_hash in field
    """

    database.query(User).where(User.login.ilike(f'%{test_hash}')).delete()
    database.query(Repo).where(Repo.name.ilike(f'%{test_hash}')).delete()
    database.query(Unit).where(Unit.name.ilike(f'%{test_hash}')).delete()
    database.query(UnitNode).where(UnitNode.topic_name.ilike(f'%{test_hash}')).delete()
    database.commit()


@pytest.fixture()
def test_users() -> list[dict]:
    return [
        {
            "login": f'test_{inc}_{test_hash}',
            "password": f'test{inc}',
        }
        for inc in range(2)
    ]
