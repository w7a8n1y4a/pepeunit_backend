import contextlib
import fcntl
import os
import shutil
import time
from pathlib import Path

from app import settings


def get_emqx_link():
    if settings.pu_mqtt_secure:
        return f"{settings.pu_mqtt_http_type}://{settings.pu_mqtt_host}"
    return f"{settings.pu_mqtt_http_type}://{settings.pu_mqtt_host}:{settings.pu_mqtt_api_port}"


def get_directory_size(directory: str) -> int:
    # analog du -sb
    return sum(
        f.stat().st_size for f in Path(directory).rglob("*") if f.is_file()
    )


def acquire_file_lock(file_lock: str):
    lock_fd = open(file_lock, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return lock_fd
    except BlockingIOError:
        lock_fd.close()
        return None


def wait_for_file_unlock(file_path, check_interval=1):
    while True:
        lock_fd = acquire_file_lock(file_path)
        if lock_fd:
            lock_fd.close()
            return
        time.sleep(check_interval)


def recreate_directory(dir_path):
    if os.path.exists(dir_path):
        shutil.rmtree(dir_path, ignore_errors=True)
    with contextlib.suppress(FileExistsError):
        os.makedirs(dir_path)
