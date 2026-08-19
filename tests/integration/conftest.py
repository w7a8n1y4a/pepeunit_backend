import asyncio
import queue
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from clickhouse_driver import Client
from sqlmodel import Session

from app import settings
from app.configs.clickhouse import get_clickhouse_client
from app.configs.db import get_session
from tests.client.mqtt import MQTTClient
from tests.integration.helpers.cleanup import clear_integration_data


@pytest.fixture(scope="session")
def database() -> Session:
    return next(get_session())


@pytest.fixture(scope="session")
def cc() -> Client:
    return next(get_clickhouse_client())


@pytest.fixture(scope="session", autouse=True)
def clean_leftovers(database) -> None:
    clear_integration_data(database)
    yield
    if settings.pu_test_integration_clear_data:
        clear_integration_data(database)


@pytest.fixture(scope="session")
def test_hash() -> str:
    from tests.integration.helpers.names import TEST_HASH

    return TEST_HASH


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
