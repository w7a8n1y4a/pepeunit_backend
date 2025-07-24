import fcntl
import os
import shutil
import time
from pathlib import Path

from app import settings


def get_emqx_link():
    if settings.mqtt_secure:
        return f'{settings.mqtt_http_type}://{settings.mqtt_host}'
    else:
        return f'{settings.mqtt_http_type}://{settings.mqtt_host}:{settings.mqtt_api_port}'


def is_valid_ip_address(domain: str) -> bool:
    ip_address_and_port = domain.split(':')

    try:
        if len(ip_address_and_port) == 2:
            port = int(ip_address_and_port[1])

            assert port >= 0 and port <= 65536

            address = ip_address_and_port[0].split('.')
            if len(address) == 4:
                valid_list = [int(number) <= 255 and int(number) >= 0 for number in address]
                assert valid_list.count(True) == 4

                return True
        elif len(ip_address_and_port) == 1:

            address = ip_address_and_port[0].split('.')
            if len(address) == 4:
                valid_list = [int(number) <= 255 and int(number) >= 0 for number in address]
                assert valid_list.count(True) == 4

                return True

    except ValueError:
        pass
    except AssertionError:
        pass

    return False


def get_directory_size(directory: str) -> int:
    total_size = 0
    for entry in os.scandir(directory):
        if entry.is_file(follow_symlinks=False):  # Игнорируем симлинки
            total_size += entry.stat().st_size
        elif entry.is_dir(follow_symlinks=False):  # Рекурсивный обход поддиректорий
            total_size += get_directory_size(entry.path)
    return total_size


def acquire_file_lock(file_lock: str):
    lock_fd = open(file_lock, 'w')
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
    try:
        os.makedirs(dir_path)
    except FileExistsError:
        pass
