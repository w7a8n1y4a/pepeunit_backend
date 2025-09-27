import logging
import time

import httpx

from app import settings


class ControlEmqx:
    current_link: str

    @staticmethod
    def get_emqx_link():
        if settings.mqtt_secure:
            return f"{settings.mqtt_http_type}://{settings.mqtt_host}"
        return f"{settings.mqtt_http_type}://{settings.mqtt_host}:{settings.mqtt_api_port}"

    def __init__(self):
        self.current_link = self.get_emqx_link()

        logging.info(f"Check state EMQX Broker {self.current_link}")

        code = 500
        inc = 0
        while code >= 400 and inc <= 60:
            code = self.check_state()

            if code >= 400:
                logging.info(
                    f"Iteration {inc}, result code - {code}. EMQX Broker not ready"
                )

            time.sleep(1)
            inc += 1

        logging.info(f"EMQX Broker {self.current_link} - Ready to work")

        self.token = self.get_bearer()

        self.headers = {
            "accept": "*/*",
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def check_state(self) -> int:
        response = httpx.get(f"{self.current_link}/api-docs/swagger.json")
        return response.status_code

    def _log_response(self, response):
        assert response.status_code < 500, (
            f"Error connect to {self.current_link}"
        )

    def get_bearer(self) -> str:
        headers = {
            "accept": "*/*",
            "Content-Type": "application/json",
        }
        data = {
            "username": settings.mqtt_username,
            "password": settings.mqtt_password,
        }
        response = httpx.post(
            f"{self.current_link}/api/v5/login", json=data, headers=headers
        )
        self._log_response(response)

        return response.json()["token"]

    async def delete_auth_hooks(self) -> None:
        for source in ["file", "http", "redis"]:
            logging.info(f"Del {source} auth hook MQTT Broker")
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"{self.current_link}/api/v5/authorization/sources/{source}",
                    headers=self.headers,
                )
            self._log_response(response)

    async def set_file_auth_hook(self) -> None:
        data = {
            "type": "file",
            "enable": True,
            "rules": """{allow, {ipaddr, "127.0.0.1"}, all, ["$SYS/#", "#"]}.\n{deny, all, subscribe, ["$SYS/#", {eq, "#"}]}.\n{deny, all}.""",
        }

        logging.info("Set ACL file auth hook MQTT Broker")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.current_link}/api/v5/authorization/sources",
                json=data,
                headers=self.headers,
            )
        self._log_response(response)

    async def set_redis_auth_hook(self) -> None:
        redis_url = settings.mqtt_redis_auth_url

        data = {
            "type": "redis",
            "enable": True,
            "server": redis_url[:-2].replace("redis://", ""),
            "redis_type": "single",
            "pool_size": 8,
            "username": "",
            "password": "",
            "database": int(redis_url.split("/")[-1]),
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

        logging.info("Set redis auth hook MQTT Broker")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.current_link}/api/v5/authorization/sources",
                json=data,
                headers=self.headers,
            )
        self._log_response(response)

    async def set_http_auth_hook(self) -> None:
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
                "enable": settings.backend_secure,
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

        logging.info("Set http auth hook MQTT Broker")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.current_link}/api/v5/authorization/sources",
                json=data,
                headers=self.headers,
            )
        self._log_response(response)

    async def set_auth_cache_ttl(self) -> None:
        data = {
            "no_match": "deny",
            "deny_action": "ignore",
            "cache": {
                "enable": True,
                "max_size": 64,
                "ttl": "10m",
                "excludes": [],
            },
        }

        logging.info("Set cache settings auth hook MQTT Broker")

        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{self.current_link}/api/v5/authorization/settings",
                json=data,
                headers=self.headers,
            )
        self._log_response(response)

    async def disable_default_listeners(self) -> None:
        async with httpx.AsyncClient() as client:
            for source in ["ssl", "ws", "wss"]:
                logging.info(f"Disable {source} listener MQTT Broker")
                response = await client.post(
                    f"{self.current_link}/api/v5/listeners/{source}:default/stop",
                    headers=self.headers,
                )
                self._log_response(response)

    async def set_tcp_listener_settings(self) -> None:
        data = {
            "acceptors": 16,
            "access_rules": ["allow all"],
            "bind": "0.0.0.0:1883",
            "bytes_rate": settings.mqtt_client_max_bytes_rate,
            "enable": True,
            "enable_authn": True,
            "id": "tcp:default",
            "max_conn_rate": settings.mqtt_max_client_connection_rate,
            "max_connections": settings.mqtt_max_clients,
            "messages_rate": settings.mqtt_client_max_messages_rate,
            "mountpoint": "",
            "proxy_protocol": False,
            "proxy_protocol_timeout": "3s",
            "running": True,
            "tcp_options": {
                "active_n": 100,
                "backlog": 1024,
                "buffer": "4KB",
                "high_watermark": "1MB",
                "keepalive": "none",
                "nodelay": True,
                "nolinger": False,
                "reuseaddr": True,
                "send_timeout": "15s",
                "send_timeout_close": True,
            },
            "type": "tcp",
            "zone": "default",
        }

        logging.info("Set settings for tcp listener")
        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{self.current_link}/api/v5/listeners/tcp:default",
                json=data,
                headers=self.headers,
            )
        self._log_response(response)

    async def set_global_mqtt_settings(self) -> None:
        data = {
            "durable_sessions": {
                "enable": False,
                "batch_size": 100,
                "heartbeat_interval": "5000ms",
                "idle_poll_interval": "10s",
                "message_retention_period": "1d",
                "session_gc_batch_size": 100,
                "session_gc_interval": "10m",
            },
            "flapping_detect": {
                "enable": False,
                "ban_time": "5m",
                "max_count": 15,
                "window_time": "1m",
            },
            "force_gc": {
                "enable": True,
                "bytes": "16MB",
                "count": 16000,
            },
            "force_shutdown": {
                "enable": True,
                "max_heap_size": "32MB",
                "max_mailbox_size": 1000,
            },
            "mqtt": {
                "max_clientid_len": settings.mqtt_max_client_id_len,
                "max_topic_alias": settings.mqtt_max_topic_alias,
                "max_qos_allowed": settings.mqtt_max_qos,
                "max_mqueue_len": settings.mqtt_max_len_message_queue,
                "max_topic_levels": settings.mqtt_max_topic_levels,
                "max_packet_size": f"{settings.mqtt_max_payload_size}KB",
                "session_expiry_interval": "2h",
                "max_subscriptions": "infinity",
                "exclusive_subscription": False,
                "use_username_as_clientid": False,
                "idle_timeout": "15s",
                "mqueue_store_qos0": True,
                "upgrade_qos": False,
                "mqueue_priorities": "disabled",
                "strict_mode": False,
                "shared_subscription": True,
                "server_keepalive": "disabled",
                "wildcard_subscription": True,
                "response_information": "",
                "shared_subscription_initial_sticky_pick": "random",
                "max_awaiting_rel": 100,
                "peer_cert_as_username": "disabled",
                "client_attrs_init": [],
                "retry_interval": "infinity",
                "retain_available": False,
                "message_expiry_interval": "infinity",
                "ignore_loop_deliver": False,
                "clientid_override": "disabled",
                "peer_cert_as_clientid": "disabled",
                "mqueue_default_priority": "lowest",
                "max_inflight": 32,
                "keepalive_multiplier": 1.5,
                "shared_subscription_strategy": "round_robin",
                "keepalive_check_interval": "30s",
                "await_rel_timeout": "300s",
            },
        }

        logging.info("Set global mqtt settings")
        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{self.current_link}/api/v5/configs/global_zone",
                json=data,
                headers=self.headers,
            )
            self._log_response(response)

            data = {
                "enable": False,
            }

            logging.info("Disable retainer")
            response = await client.put(
                f"{self.current_link}/api/v5/mqtt/retainer",
                json=data,
                headers=self.headers,
            )
            self._log_response(response)
