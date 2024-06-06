import base64
import json
import logging

import httpx

from app import settings


def set_emqx_auth_hook() -> None:

    basic_auth = base64.b64encode((settings.mqtt_api_key + ':' + settings.mqtt_secret_key).encode('utf-8')).decode(
        'ascii'
    )

    headers = {
        'accept': '*/*',
        'Authorization': f"Basic {basic_auth}",
        'Content-Type': 'application/json'
    }

    data = {
        "body": {
            "token": "${username}",
            "topic": "${topic}"
        },
        "connect_timeout": "15s",
        "enable": True,
        "enable_pipelining": 100,
        "headers": {
            "content-type": "application/json"
        },
        "method": "post",
        "pool_size": 8,
        "request_timeout": "30s",
        "ssl": {
            "ciphers": [],
            "depth": 10,
            "enable": True,
            "hibernate_after": "5s",
            "log_level": "notice",
            "reuse_sessions": True,
            "secure_renegotiate": True,
            "verify": "verify_none",
            "versions": [
                "tlsv1.3",
                "tlsv1.2"
            ]
        },
        "type": "http",
        "url": f"https://{settings.backend_domain}{settings.app_prefix}{settings.api_v1_prefix}/units/auth"
    }

    response = httpx.post(
        f'https://{settings.mqtt_host}/api/v5/authorization/sources',
        json=data,
        headers=headers
    )

    try:
        result = response.json()
    except json.decoder.JSONDecodeError:
        result = 'Authorization source created successfully'

    logging.info(result)


def set_emqx_auth_cache_ttl() -> None:

    basic_auth = base64.b64encode((settings.mqtt_api_key + ':' + settings.mqtt_secret_key).encode('utf-8')).decode(
        'ascii'
    )

    headers = {
        'accept': 'application/json',
        'Authorization': f"Basic {basic_auth}",
        'Content-Type': 'application/json'
    }

    data = {
        "no_match": "deny",
        "deny_action": "ignore",  # ignore = not send other sub; disconnect = del connection over mqtt
        "cache": {
            "enable": True,
            "max_size": 64,
            "ttl": "10m",
            "excludes": []
        }
    }

    response = httpx.put(
        f'https://{settings.mqtt_host}/api/v5/authorization/settings',
        json=data,
        headers=headers
    )

    logging.info(response.json())
