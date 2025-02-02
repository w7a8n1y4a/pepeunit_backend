import logging
import time

import httpx

from app import settings


class ControlEmqx:
    current_link: str

    @staticmethod
    def get_emqx_link():
        if settings.mqtt_secure:
            return f'{settings.mqtt_http_type}://{settings.mqtt_host}'
        else:
            return f'{settings.mqtt_http_type}://{settings.mqtt_host}:{settings.mqtt_api_port}'

    def __init__(self):

        self.current_link = self.get_emqx_link()

        logging.info(f'Check state EMQX Broker {self.current_link}')

        code = 500
        inc = 0
        while code >= 400 and inc <= 60:
            code = self.check_state()

            if code >= 400:
                logging.info(f'Iteration {inc}, result code - {code}. EMQX Broker not ready')

            time.sleep(1)
            inc += 1

        logging.info(f'EMQX Broker {self.current_link} - Ready to work')

        self.token = self.get_bearer()

        self.headers = {
            "accept": "*/*",
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def check_state(self) -> int:
        response = httpx.get(f'{self.current_link}/api-docs/swagger.json')
        return response.status_code

    def _log_response(self, response):
        assert response.status_code < 500, f'Error connect to {self.current_link}'

    def get_bearer(self) -> str:
        headers = {
            "accept": "*/*",
            "Content-Type": "application/json",
        }
        data = {
            'username': settings.mqtt_username,
            'password': settings.mqtt_password,
        }
        response = httpx.post(f'{self.current_link}/api/v5/login', json=data, headers=headers)
        self._log_response(response)

        return response.json()['token']

    def delete_auth_hooks(self) -> None:
        for source in ["file", "http", "redis"]:
            logging.info(f"Del {source} auth hook MQTT Broker")
            response = httpx.delete(f'{self.current_link}/api/v5/authorization/sources/{source}', headers=self.headers)
            self._log_response(response)

    def set_file_auth_hook(self) -> None:
        data = {
            "type": "file",
            "enable": True,
            "rules": """{allow, {ipaddr, "127.0.0.1"}, all, ["$SYS/#", "#"]}.\n{deny, all, subscribe, ["$SYS/#", {eq, "#"}]}.\n{deny, all}.""",
        }

        logging.info(f'Set ACL file auth hook MQTT Broker')
        response = httpx.post(f'{self.current_link}/api/v5/authorization/sources', json=data, headers=self.headers)
        self._log_response(response)

    def set_redis_auth_hook(self) -> None:
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
                "enable": False,
                "versions": ["tlsv1.3", "tlsv1.2"],
                "verify": "verify_peer",
                "reuse_sessions": True,
                "depth": 10,
                "secure_renegotiate": True,
                "log_level": "emergency",
                "hibernate_after": "12m",
            },
            "cmd": "HGETALL mqtt_acl:${username}",
        }

        logging.info(f'Set redis auth hook MQTT Broker')
        response = httpx.post(f'{self.current_link}/api/v5/authorization/sources', json=data, headers=self.headers)
        self._log_response(response)

    def set_http_auth_hook(self) -> None:
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
                "enable": settings.secure,
                "versions": ["tlsv1.3", "tlsv1.2"],
                "verify": "verify_none",
                "reuse_sessions": True,
                "secure_renegotiate": True,
                "log_level": "notice",
                "hibernate_after": "5s",
                "depth": 10,
            },
            "type": "http",
            "url": f"{settings.backend_link_prefix_and_v1}/units/auth",
        }

        logging.info(f'Set http auth hook MQTT Broker')
        response = httpx.post(f'{self.current_link}/api/v5/authorization/sources', json=data, headers=self.headers)
        self._log_response(response)

    def set_auth_cache_ttl(self) -> None:
        data = {
            "no_match": "deny",
            "deny_action": "ignore",
            "cache": {"enable": True, "max_size": 64, "ttl": "10m", "excludes": []},
        }

        logging.info(f'Set cache settings auth hook MQTT Broker')
        response = httpx.put(f'{self.current_link}/api/v5/authorization/settings', json=data, headers=self.headers)
        self._log_response(response)
