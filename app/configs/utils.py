import base64
import json
import logging
from pathlib import Path

import httpx

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


def check_emqx_state() -> None:
    logging.info(f'Check state EMQX Broker {settings.mqtt_host}:{settings.mqtt_port}')
    response = httpx.get(f'{get_emqx_link()}/api-docs/swagger.json')

    assert response.status_code < 400, f'Error connect to {settings.mqtt_host}:{settings.mqtt_port}'


def del_emqx_auth_hooks() -> None:
    basic_auth = base64.b64encode((settings.mqtt_api_key + ':' + settings.mqtt_secret_key).encode('utf-8')).decode(
        'ascii'
    )

    headers = {'accept': '*/*', 'Authorization': f"Basic {basic_auth}", 'Content-Type': 'application/json'}

    logging.info(f'Del auth hook mqtt server {settings.mqtt_host}:{settings.mqtt_port}')
    response = httpx.delete(f'{get_emqx_link()}/api/v5/authorization/sources/http', headers=headers)
    assert response.status_code < 500, f'Error connect to {settings.mqtt_host}:{settings.mqtt_port}'
    response = httpx.delete(f'{get_emqx_link()}/api/v5/authorization/sources/redis', headers=headers)
    assert response.status_code < 500, f'Error connect to {settings.mqtt_host}:{settings.mqtt_port}'


def set_redis_emqx_auth_hook() -> None:

    basic_auth = base64.b64encode((settings.mqtt_api_key + ':' + settings.mqtt_secret_key).encode('utf-8')).decode(
        'ascii'
    )

    headers = {'accept': '*/*', 'Authorization': f"Basic {basic_auth}", 'Content-Type': 'application/json'}

    redis_url = settings.redis_mqtt_auth_url

    data = {
        "type": "redis",
        "enable": True,
        "server": redis_url[:-2].replace('redis://', ''),
        "redis_type": "single",
        "pool_size": 8,
        "username": "",
        "password": "",
        "database": int(redis_url.split('/')[-1]),
        "auto_reconnect": True,
        "ssl": {
            "cacertfile": "string",
            "cacerts": False,
            "certfile": "",
            "keyfile": "",
            "verify": "verify_peer",
            "reuse_sessions": True,
            "depth": 10,
            "password": "",
            "versions": ["tlsv1.3", "tlsv1.2"],
            "ciphers": [],
            "secure_renegotiate": True,
            "log_level": "emergency",
            "hibernate_after": "12m",
            "enable": False,
            "server_name_indication": "disable",
        },
        "cmd": "HGETALL mqtt_acl:${username}",
    }

    logging.info(f'Set redis auth hook to mqtt server {settings.mqtt_host}:{settings.mqtt_port}')
    response = httpx.post(f'{get_emqx_link()}/api/v5/authorization/sources', json=data, headers=headers)

    assert response.status_code < 500, f'Error connect to {settings.mqtt_host}:{settings.mqtt_port}'

    try:
        result = response.json()
    except json.decoder.JSONDecodeError:
        result = 'Success auth hook create'

    logging.info(result)


def set_http_emqx_auth_hook() -> None:

    basic_auth = base64.b64encode((settings.mqtt_api_key + ':' + settings.mqtt_secret_key).encode('utf-8')).decode(
        'ascii'
    )

    headers = {'accept': '*/*', 'Authorization': f"Basic {basic_auth}", 'Content-Type': 'application/json'}

    data = {
        "body": {"token": "${username}", "topic": "${topic}"},
        "connect_timeout": "15s",
        "enable": True,
        "enable_pipelining": 100,
        "headers": {"content-type": "application/json"},
        "method": "post",
        "pool_size": 8,
        "request_timeout": "30s",
        "ssl": {
            "ciphers": [],
            "depth": 10,
            "enable": settings.secure,
            "hibernate_after": "5s",
            "log_level": "notice",
            "reuse_sessions": True,
            "secure_renegotiate": True,
            "verify": "verify_none",
            "versions": ["tlsv1.3", "tlsv1.2"],
        },
        "type": "http",
        "url": f"{settings.backend_link_prefix_and_v1}/units/auth",
    }

    logging.info(f'Set http auth hook to mqtt server {settings.mqtt_host}:{settings.mqtt_port}')
    response = httpx.post(f'{get_emqx_link()}/api/v5/authorization/sources', json=data, headers=headers)

    assert response.status_code < 500, f'Error connect to {settings.mqtt_host}:{settings.mqtt_port}'

    try:
        result = response.json()
    except json.decoder.JSONDecodeError:
        result = 'Success auth hook create'

    logging.info(result)


def set_emqx_auth_cache_ttl() -> None:

    basic_auth = base64.b64encode((settings.mqtt_api_key + ':' + settings.mqtt_secret_key).encode('utf-8')).decode(
        'ascii'
    )

    headers = {'accept': 'application/json', 'Authorization': f"Basic {basic_auth}", 'Content-Type': 'application/json'}

    data = {
        "no_match": "deny",
        "deny_action": "ignore",  # ignore = not send other sub; disconnect = del connection over mqtt
        "cache": {"enable": True, "max_size": 64, "ttl": "10m", "excludes": []},
    }

    logging.info(f'Set cache settings auth hook to mqtt server {settings.mqtt_host}:{settings.mqtt_port}')
    response = httpx.put(f'{get_emqx_link()}/api/v5/authorization/settings', json=data, headers=headers)

    assert response.status_code < 500, f'Error connect to {settings.mqtt_host}:{settings.mqtt_port}'

    logging.info(response.json())


def get_directory_size(directory: str) -> int:
    return sum(f.stat().st_size for f in Path(directory).rglob('*') if f.is_file())
