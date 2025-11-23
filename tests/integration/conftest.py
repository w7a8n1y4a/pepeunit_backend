import asyncio
import hashlib
import os
import queue
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from json import JSONDecodeError

import pytest
from clickhouse_driver import Client
from sqlmodel import Session

from app import settings
from app.configs.clickhouse import get_clickhouse_client
from app.configs.db import get_session
from app.domain.repository_registry_model import RepositoryRegistry
from app.domain.user_model import User
from app.dto.enum import VisibilityLevel
from app.schemas.pydantic.repository_registry import Credentials
from app.services.validators import is_valid_json
from tests.client.mqtt import MQTTClient

test_hash = hashlib.md5(settings.pu_domain.encode("utf-8")).hexdigest()[:5]


def pytest_configure():
    pytest.test_hash = test_hash
    pytest.users = []
    pytest.user_tokens_dict = {}
    pytest.repository_registries = []
    pytest.repos = []
    pytest.units = []
    pytest.edges = []
    pytest.permissions = []
    pytest.dashboards = []
    pytest.panels = []
    pytest.delete_panel = []


@pytest.fixture(scope="session")
def database() -> Session:
    return next(get_session())


@pytest.fixture(scope="session")
def cc() -> Client:
    return next(get_clickhouse_client())


@pytest.fixture
def clear_database(database) -> None:
    """
    clear all entity in database with test_hash in field
    """

    # del files
    shutil.rmtree("tmp/test_units", ignore_errors=True)
    shutil.rmtree("tmp/test_units_tar_tgz", ignore_errors=True)

    for item in os.listdir(settings.pu_save_repo_path):
        item_path = os.path.join(settings.pu_save_repo_path, item)
        if os.path.isdir(item_path):
            shutil.rmtree(item_path, ignore_errors=True)

    database.query(RepositoryRegistry).where(
        RepositoryRegistry.repository_url.in_(
            [
                "https://github.com/w7a8n1y4a/github_unit_priv_test.git",
                "https://git.pepemoss.com/pepe/pepeunit/units/gitlab_unit_priv_test.git",
                "https://github.com/w7a8n1y4a/github_unit_pub_test.git",
                "https://git.pepemoss.com/pepe/pepeunit/units/gitlab_unit_pub_test.git",
                "https://git.pepemoss.com/pepe/pepeunit/units/universal_test_unit.git",
            ]
        )
    ).delete()

    database.query(User).where(User.login.ilike(f"%{test_hash}%")).delete()
    database.commit()


@pytest.fixture()
def test_users() -> list[dict]:
    return [
        {
            "login": f"test_{inc}_{test_hash}",
            "password": f"testtest{inc}",
        }
        for inc in range(2)
    ]


@pytest.fixture()
def test_external_repository() -> list[dict]:
    # get private repository
    test_external_repository = []
    try:
        data = is_valid_json(
            settings.pu_test_integration_private_repo_json, "Private Repo"
        )
        if isinstance(data, str):
            data = is_valid_json(data, "Private Repo")
    except JSONDecodeError:
        assert False

    test_external_repository.extend(data["data"])

    # add public repository
    test_external_repository.extend(
        [
            {
                "is_public": True,
                "link": "https://github.com/w7a8n1y4a/github_unit_pub_test.git",
                "platform": "Github",
            },
            {
                "is_public": True,
                "link": "https://git.pepemoss.com/pepe/pepeunit/units/gitlab_unit_pub_test.git",
                "platform": "Gitlab",
                "compile": True,
            },
            {
                "is_public": True,
                "link": "https://git.pepemoss.com/pepe/pepeunit/units/universal_test_unit.git",
                "platform": "Gitlab",
            },
        ]
    )

    return [
        {
            "repository_url": repo["link"],
            "is_public_repository": repo["is_public"],
            "platform": repo["platform"],
            "is_compilable_repo": repo["compile"] if "compile" in repo else False,
            "credentials": (
                None
                if repo["is_public"]
                else {"username": repo["username"], "pat_token": repo["pat_token"]}
            ),
        }
        for inc, repo in enumerate(test_external_repository)
    ]


@pytest.fixture()
def test_repos() -> list[dict]:
    # get private repository
    test_repos = []
    try:
        data = is_valid_json(
            settings.pu_test_integration_private_repo_json, "Private Repo"
        )
        if isinstance(data, str):
            data = is_valid_json(data, "Private Repo")
    except JSONDecodeError:
        assert False

    test_repos.extend(data["data"])

    # add public repository
    test_repos.extend(
        [
            {
                "type": VisibilityLevel.PUBLIC,
                "is_public": True,
                "link": "https://github.com/w7a8n1y4a/github_unit_pub_test.git",
                "platform": "Github",
            },
            {
                "type": VisibilityLevel.PUBLIC,
                "is_public": True,
                "link": "https://git.pepemoss.com/pepe/pepeunit/units/gitlab_unit_pub_test.git",
                "platform": "Gitlab",
                "compile": True,
            },
            {
                "type": VisibilityLevel.PUBLIC,
                "is_public": True,
                "link": "https://github.com/w7a8n1y4a/github_unit_pub_test.git",
                "platform": "Github",
                "compile": True,
            },
            {
                "type": VisibilityLevel.PUBLIC,
                "is_public": True,
                "link": "https://git.pepemoss.com/pepe/pepeunit/units/universal_test_unit.git",
                "platform": "Gitlab",
            },
            {
                "type": VisibilityLevel.INTERNAL,
                "is_public": True,
                "link": "https://git.pepemoss.com/pepe/pepeunit/units/universal_test_unit.git",
                "platform": "Gitlab",
            },
            {
                "type": VisibilityLevel.PRIVATE,
                "is_public": True,
                "link": "https://git.pepemoss.com/pepe/pepeunit/units/universal_test_unit.git",
                "platform": "Gitlab",
            },
            {
                "type": VisibilityLevel.PUBLIC,
                "is_public": True,
                "link": "https://git.pepemoss.com/pepe/pepeunit/units/universal_test_unit.git",
                "platform": "Gitlab",
                "compile": True,
            },
        ]
    )
    return [
        {
            "visibility_level": repo["type"],
            "name": f"test_{inc}_{test_hash}",
            "repository_url": repo["link"],
            "is_public_repository": repo["is_public"],
            "platform": repo["platform"],
            "is_compilable_repo": repo["compile"] if "compile" in repo else False,
            "credentials": (
                None
                if repo["is_public"]
                else Credentials(username=repo["username"], pat_token=repo["pat_token"])
            ),
            "is_auto_update_repo": True,
        }
        for inc, repo in enumerate(test_repos)
    ]


@pytest.fixture()
def test_dashboards() -> list[str]:
    return [f"test_{inc}_{test_hash}" for inc in range(2)]


class ClientEmulatorThread(threading.Thread):
    units: int

    def __init__(self):
        super().__init__(daemon=True)
        self.task_queue = queue.Queue()
        self.result_queue = queue.Queue()
        self.running = True
        self.executor = ThreadPoolExecutor(max_workers=10)
        self.clients = []

    def run(self):
        while self.running:
            try:
                task = self.task_queue.get(timeout=1)

                if isinstance(task, list):
                    for unit in task:
                        thread = threading.Thread(
                            target=self.start_mqtt_client, args=(unit,), daemon=True
                        )
                        self.clients.append(thread)
                        thread.start()

                    self.result_queue.put({"run_client": [unit.uuid for unit in task]})
                if task == "STOP":
                    break

                self.result_queue.put(task)
            except queue.Empty:
                pass

    def start_mqtt_client(self, unit):
        mqtt_client = MQTTClient(unit)
        asyncio.run(mqtt_client.run())

    def stop(self):
        self.running = False
        self.task_queue.put("STOP")

        self.executor.shutdown(wait=True)


@pytest.fixture(scope="session")
def client_emulator():
    emulator = ClientEmulatorThread()
    emulator.start()
    yield emulator
    emulator.stop()
    emulator.join()
