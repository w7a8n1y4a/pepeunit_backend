import asyncio
import json
import threading
import time
from collections import namedtuple
from typing import Optional

from pepeunit_client import PepeunitClient
from pepeunit_client.enums import SearchScope, SearchTopicType, RestartMode


class MQTTClient:
    def __init__(self, unit):
        self.unit = unit
        self.client: Optional[PepeunitClient] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None

        self.env_file = f"tmp/test_units/{unit.uuid}/env.json"
        self.schema_file = f"tmp/test_units/{unit.uuid}/schema.json"
        self.log_file = f"tmp/test_units/{unit.uuid}/log.json"

        self.client = PepeunitClient(
            env_file_path=self.env_file,
            schema_file_path=self.schema_file,
            log_file_path=self.log_file,
            enable_mqtt=True,
            enable_rest=True,
            restart_mode=RestartMode.ENV_SCHEMA_ONLY,
            skip_version_check=True
        )

        self.client.set_mqtt_input_handler(self.mqtt_input_handler)

    @staticmethod
    def mqtt_input_handler(client: PepeunitClient, msg):
        try:
            topic_parts = msg.topic.split("/")

            if len(topic_parts) == 3:
                domain, unit_node_uuid, _ = topic_parts

                topic_name = client.schema.find_topic_by_unit_node(
                    msg.topic, SearchTopicType.FULL_NAME, SearchScope.INPUT
                )

                if topic_name == "input/pepeunit":
                    value = msg.payload
                    try:
                        value = int(value)
                        if value == 0:
                            log_state = {
                                "value": value,
                                "input_topic": topic_parts,
                                "timestamp": time.time(),
                            }
                            with open(
                                f"tmp/test_units/{client.settings.unit_uuid}/log_state.json", "w"
                            ) as f:
                                json.dump(log_state, f, indent=4)

                            client.publish_to_topics("output/pepeunit", str(value))

                    except ValueError:
                        pass

        except Exception as e:
            print(f"Error in mqtt_input_handler: {e}")

    async def publish_messages(self):
        msg_count = 1
        while self._running:
            try:
                current_time = time.time()
                if (
                    current_time - self.client.settings.DELAY_PUB_MSG
                ) >= self.client.settings.DELAY_PUB_MSG:
                    msg = f"{msg_count // 10}"
                    self.client.publish_to_topics("output/pepeunit", msg)
                    msg_count += 1

                self.client._base_mqtt_output_handler()

                await asyncio.sleep(0.25)

            except Exception as e:
                self.client.logger.error(f"Error in publish_messages: {e}")
                await asyncio.sleep(1)

    async def run(self):
        try:
            self._running = True
            self.client.mqtt_client.connect()
            self.client.subscribe_all_schema_topics()
            await self.publish_messages()
        except Exception as e:
            self.client.logger.error(f"Exception: {e}")
        finally:
            self._running = False

    def stop(self):
        self._running = False
        if self.client:
            self.client.logger.info("Stopping Pepeunit client")


if __name__ == "__main__":
    UnitType = namedtuple("Unit", ["uuid"])
    test_unit = UnitType(uuid="a3946222-3ac9-4d2e-b366-5c258cf70471")

    mqtt_client = MQTTClient(test_unit)
    asyncio.run(mqtt_client.run())
