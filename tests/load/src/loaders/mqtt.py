import asyncio
import time
import uuid

from paho.mqtt import client as mqtt_client

from app.utils.utils import generate_random_string
from tests.load.src.dto.config import LoadTestConfig


class MQTTLoadTest:

    start_time: float

    def __init__(self, config: LoadTestConfig, units):
        self.config = config
        self.units = units
        self.clients = []

    async def connect_mqtt(self, token, broker, port):
        client = mqtt_client.Client(mqtt_client.CallbackAPIVersion.VERSION1, str(uuid.uuid4()))

        def on_connect(client, userdata, flags, rc):
            pass

        client.username_pw_set(token, '')
        client.on_connect = on_connect
        client.connect(broker, port)
        return client

    async def publish(self, client, unit):
        topic_dict = self.get_dict_by_topic(unit, 'output/pepeunit')
        topic = f"{unit['env']['PEPEUNIT_URL']}/{topic_dict['uuid']}/pepeunit"
        client.loop_start()

        message = generate_random_string(self.config.message_size)
        count = 0

        while time.time() - self.start_time < self.config.duration:

            if self.config.value_type == 'Text':
                if count % self.config.duplicate_count == 0:
                    message = generate_random_string(self.config.message_size)
            else:
                message = count // self.config.duplicate_count

            client.publish(topic, message)
            count += 1
            await asyncio.sleep(1 / self.config.rps)

        return count

    async def start_test(self):
        tasks = []
        for unit in self.units:
            client = await self.connect_mqtt(
                unit['env']['PEPEUNIT_TOKEN'], unit['env']['MQTT_URL'], unit['env']['MQTT_PORT']
            )
            self.clients.append(client)
            tasks.append(asyncio.create_task(self.publish(client, unit)))

        self.start_time = time.time()
        batch_data = await asyncio.gather(*tasks)

        return sum(batch_data)

    @staticmethod
    def get_dict_by_topic(unit, topic_name):
        return next((item for item in unit['unit_nodes'] if item.get('topic_name') == topic_name), None)
