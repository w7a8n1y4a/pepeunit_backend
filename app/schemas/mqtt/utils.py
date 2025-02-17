import json
import multiprocessing
import os
import time

import psutil

from app import settings
from app.configs.errors import app_errors
from app.repositories.enum import ReservedStateKey
from app.schemas.pydantic.unit import UnitStateRead


def get_topic_split(topic: str) -> tuple[str, ...]:
    return tuple(topic.split('/'))


def get_only_reserved_keys(input_dict: dict) -> dict:
    reserved_keys = {key.value for key in ReservedStateKey}
    filtered_dict = {key: value for key, value in input_dict.items() if key in reserved_keys}
    return UnitStateRead(**filtered_dict).dict()


def publish_to_topic(topic: str, msg: dict or str) -> None:
    from app.schemas.mqtt.topic import mqtt

    try:
        mqtt.publish(topic, json.dumps(msg) if isinstance(msg, dict) else msg)
    except AttributeError:
        app_errors.mqtt_error.raise_exception(
            'Error when publish message to topic {}: {}'.format(topic, 'Backend MQTT session is invalid')
        )
    except Exception as ex:
        app_errors.mqtt_error.raise_exception('Error when publish message to topic {}: {}'.format(topic, ex))


worker_pids = multiprocessing.Manager().list()


def get_all_worker_pids(topic_name: str):
    current_pid = os.getpid()
    parent_pid = os.getppid()
    master_process = psutil.Process(parent_pid)

    lock = multiprocessing.Lock()
    with lock:
        if current_pid not in worker_pids or len(worker_pids) != settings.backend_worker_count:
            for p in master_process.children():
                cmd = " ".join(p.cmdline()) if p.cmdline() else ""
                if "resource_tracker" not in cmd:
                    worker_pids.append(p.pid)

            worker_pids.sort()

    return worker_pids.index(current_pid) == hash(topic_name) % len(worker_pids)
