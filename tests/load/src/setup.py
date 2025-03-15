import httpx

from tests.load.src.clients.rest_client import RestClient
from tests.load.src.dto.config import LoadTestConfig


class MqttTestPreparation:

    repo: dict
    units: list[dict]
    rest_client: RestClient
    mqtt_token: str

    def __init__(self, config: LoadTestConfig):
        self.config = config
        self.rest_client = RestClient(config)

    async def setup(self):
        self.repo = self.rest_client.get_repo()
        self.units = await self.rest_client.generation_units(self.repo)
        self.mqtt_token = self.get_bearer()

    def teardown(self):
        pass

    def get_bearer(self) -> str:
        headers = {
            "accept": "*/*",
            "Content-Type": "application/json",
        }
        data = {
            'username': self.rest_client.config.mqtt_admin,
            'password': self.rest_client.config.mqtt_password,
        }

        mqtt_url = self.units[0]['env']['MQTT_URL']
        mqtt_http_type = self.units[0]['env']['HTTP_TYPE']

        response = httpx.post(f"{mqtt_http_type}://{mqtt_url}/api/v5/login", json=data, headers=headers)

        return response.json()['token']

    def is_backend_subs(self):
        headers = {
            "accept": "*/*",
            "Authorization": f"Bearer {self.mqtt_token}",
            "Content-Type": "application/json",
        }

        mqtt_url = self.units[0]['env']['MQTT_URL']
        mqtt_http_type = self.units[0]['env']['HTTP_TYPE']

        link = f"{mqtt_http_type}://{mqtt_url}/api/v5/subscriptions?page=1&limit=50&qos=0&topic={self.units[0]['env']['PEPEUNIT_URL']}%2F%2B%2Fpepeunit"

        data = httpx.get(link, headers=headers)

        print()

        return data.json()['meta']['count'] == 1
