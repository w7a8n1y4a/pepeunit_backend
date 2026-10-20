import logging

import httpx

from app import runtime
from tests.load.src.clients.rest_client import RestClient
from tests.load.src.dto.config import LoadTestConfig


class MqttTestPreparation:
    registry: dict
    units: list[dict]
    rest_client: RestClient
    mqtt_token: str

    def __init__(self, config: LoadTestConfig):
        self.config = config
        self.rest_client = RestClient(config)

    async def setup(self):
        self.registry = self.rest_client.get_registry()
        self.units = await self.rest_client.generation_units(self.registry)
        self.mqtt_token = self.get_bearer()

    def teardown(self):
        pass

    def get_bearer(self) -> str:
        headers = {
            "accept": "*/*",
            "Content-Type": "application/json",
        }
        data = {
            "username": self.rest_client.config.mqtt_admin,
            "password": self.rest_client.config.mqtt_password,
        }

        pu_mqtt_host = self.units[0]["env"]["PU_MQTT_HOST"]
        pu_mqtt_http_type = self.units[0]["env"]["PU_HTTP_TYPE"]

        response = httpx.post(
            f"{pu_mqtt_http_type}://{pu_mqtt_host}/api/v5/login",
            json=data,
            headers=headers,
            timeout=runtime.get().http_timeout(),
        )

        return response.json()["token"]

    def is_backend_subs(self):
        headers = {
            "accept": "*/*",
            "Authorization": f"Bearer {self.mqtt_token}",
            "Content-Type": "application/json",
        }

        pu_mqtt_host = self.units[0]["env"]["PU_MQTT_HOST"]
        pu_mqtt_http_type = self.units[0]["env"]["PU_HTTP_TYPE"]

        link = f"{pu_mqtt_http_type}://{pu_mqtt_host}/api/v5/subscriptions?page=1&limit=50&qos=0&topic={self.units[0]['env']['PU_DOMAIN']}%2F%2B%2Fpepeunit"

        data = httpx.get(link, headers=headers, timeout=runtime.get().http_timeout())

        count = data.json()["meta"]["count"]
        logging.warning(f"Count mqtt client with sub topics: {count}")

        return count >= 1
