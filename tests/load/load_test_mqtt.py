import asyncio
import hashlib
import json
import logging
import math
import multiprocessing
import os
import signal
import sys
import threading
import time

import psutil

from app import settings
from tests.load.src.dto.config import LoadTestConfig
from tests.load.src.loaders.mqtt import MQTTLoadTest
from tests.load.src.setup import MqttTestPreparation

logging.basicConfig(level=logging.WARNING)


def handler(signum, frame):
    sys.exit(1)


signal.signal(signal.SIGTERM, handler)


class LoadTester:
    def __init__(self, config: LoadTestConfig, preparation: MqttTestPreparation):
        self.config = config
        self.preparation = preparation

    async def run(self):
        await self.run_mqtt_test()

        sys.exit(0)

    def split_units(self):
        num_units = len(self.preparation.units)
        num_workers = min(self.config.workers, num_units)

        batch_size = math.ceil(num_units / num_workers)
        return [self.preparation.units[i : i + batch_size] for i in range(0, num_units, batch_size)]

    def run_mqtt_batch(self, units_batch):
        mqtt_test = MQTTLoadTest(self.config, units_batch)
        return asyncio.run(mqtt_test.start_test())

    async def run_mqtt_test(self):
        num_workers = self.config.workers
        unit_batches = self.split_units()
        duration = self.config.duration

        def check_backend():
            start_time = time.time()
            while time.time() - start_time < duration:
                time.sleep(1)
                if not self.preparation.is_backend_subs():
                    logging.warning(f'Backend crash on {round(time.time()-start_time, 2)} s')

                    terminate_all_children()
                    os.kill(os.getpid(), signal.SIGTERM)

        def terminate_all_children():
            parent_process = psutil.Process(os.getpid())
            children = parent_process.children(recursive=True)

            for child in children:
                child.terminate()
            for child in children:
                child.wait()

        check_backend_thread = threading.Thread(target=check_backend, daemon=True)

        check_backend_thread.start()

        with multiprocessing.Pool(processes=num_workers) as pool:
            try:
                results = pool.map(self.run_mqtt_batch, unit_batches)

                check_backend_thread.join()

                logging.warning(
                    f'Backend sustained {round(sum(results)/self.config.duration, 2)} rps for {self.config.duration} seconds'
                )

            except Exception as ex:
                print(ex)

    def save_report(self, data):
        with open(self.report_path, 'w') as f:
            json.dump(data, f)


async def main():
    url = f'{settings.backend_http_type}://{settings.backend_domain}'

    config = LoadTestConfig(
        url=url,
        duration=settings.test_load_mqtt_duration,
        unit_count=settings.test_load_mqtt_unit_count,
        rps=settings.test_load_mqtt_rps,
        duplicate_count=settings.test_load_mqtt_duplicate_count,
        message_size=settings.test_load_mqtt_message_size,
        workers=settings.test_load_mqtt_workers,
        mqtt_admin=settings.mqtt_username,
        mqtt_password=settings.mqtt_password,
        test_hash=hashlib.md5(url.encode('utf-8')).hexdigest()[:10],
    )

    preparation = MqttTestPreparation(config)
    await preparation.setup()

    tester = LoadTester(config, preparation)
    await tester.run()


if __name__ == "__main__":
    asyncio.run(main())
