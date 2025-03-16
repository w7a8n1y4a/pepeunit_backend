import asyncio
import json
import logging
import os
import shutil
import sys
import time
import uuid
import zlib

import httpx
import psutil
from paho.mqtt import client as mqtt_client

from tests.client.config import BaseConfig


class MQTTClient:
    def __init__(self, unit):
        self.client = None
        self.unit = unit
        self.settings = self.get_settings()

    def get_settings(self):
        with open(f"tmp/test_units/{self.unit.uuid}/env.json", 'r') as f:
            json_env = json.loads(f.read())

        return BaseConfig(**json_env)

    async def connect_mqtt(self):
        self.client = mqtt_client.Client(mqtt_client.CallbackAPIVersion.VERSION1, str(uuid.uuid4()))

        self.client.username_pw_set(self.settings.PEPEUNIT_TOKEN, '')
        self.client.on_connect = self.on_connect
        self.client.on_subscribe = self.on_subscribe
        self.client.on_message = self.on_message

        self.client.connect(self.settings.MQTT_URL, self.settings.MQTT_PORT)
        return self.client

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print("Connected to MQTT Broker!")
        else:
            print(f"Failed to connect, return code {rc}\n")
        client.subscribe([(topic, 0) for topic in self.get_input_topics()])

    def on_subscribe(self, client, userdata, mid, granted_qos):
        print("Subscribed: " + str(mid) + " " + str(granted_qos))

    def on_message(self, client, userdata, msg):
        struct_topic = self.get_topic_split(msg.topic)
        print(struct_topic)

        if len(struct_topic) == 5:
            backend_domain, destination, unit_uuid, topic_name, *_ = struct_topic

            if destination == 'input_base_topic' and topic_name == 'update':
                self.handle_update(msg)
            elif destination == 'input_base_topic' and topic_name == 'schema_update':
                self.handle_schema_update()
        elif len(struct_topic) == 3:
            self.handle_input_message(client, msg, struct_topic)

    def handle_update(self, msg):
        update_dict = json.loads(msg.payload.decode())
        new_version = update_dict['NEW_COMMIT_VERSION']
        wbits = 9
        level = 9

        headers = {'accept': 'application/json', 'x-auth-token': self.settings.PEPEUNIT_TOKEN.encode()}

        pepe_url = (
            f"{self.settings.HTTP_TYPE}://{self.settings.PEPEUNIT_URL}{self.settings.PEPEUNIT_APP_PREFIX}"
            f"{self.settings.PEPEUNIT_API_ACTUAL_PREFIX}/units/firmware/tgz/{self.unit.uuid}"
            f"?wbits={wbits}&level={level}"
        )

        new_version_path = f'tmp/test_units/{self.unit.uuid}/update'
        shutil.rmtree(new_version_path, ignore_errors=True)
        os.mkdir(new_version_path)

        if 'COMPILED_FIRMWARE_LINK' in update_dict:
            self.download_and_extract(update_dict['COMPILED_FIRMWARE_LINK'], new_version_path, 'zip')

        if self.settings.COMMIT_VERSION != new_version:
            self.download_and_extract(pepe_url, new_version_path, 'tgz', headers)

        shutil.copytree(new_version_path, f'tmp/test_units/{self.unit.uuid}', dirs_exist_ok=True)

        self.settings = self.get_settings()

    def download_and_extract(self, url, extract_path, archive_format, headers=None):
        r = httpx.get(url=url, headers=headers) if headers else httpx.get(url=url)
        filepath = f'tmp/test_units/{self.unit.uuid}/update.{archive_format}'
        with open(filepath, 'wb') as f:
            f.write(r.content)

        if archive_format == 'tgz':
            with open(filepath, 'rb') as f:
                producer = zlib.decompressobj(wbits=9)
                tar_data = producer.decompress(f.read()) + producer.flush()
                tar_filepath = f'tmp/test_units/{self.unit.uuid}/update.tar'
                with open(tar_filepath, 'wb') as tar_file:
                    tar_file.write(tar_data)
                shutil.unpack_archive(tar_filepath, extract_path, 'tar')
        else:
            shutil.unpack_archive(filepath, extract_path, archive_format)

    def handle_schema_update(self):
        headers = {'accept': 'application/json', 'x-auth-token': self.settings.PEPEUNIT_TOKEN.encode()}
        url = (
            f"{self.settings.HTTP_TYPE}://{self.settings.PEPEUNIT_URL}{self.settings.PEPEUNIT_APP_PREFIX}"
            f"{self.settings.PEPEUNIT_API_ACTUAL_PREFIX}/units/get_current_schema/{self.unit.uuid}"
        )
        r = httpx.get(url=url, headers=headers)
        with open(f'tmp/test_units/{self.unit.uuid}/schema.json', 'w') as f:
            f.write(json.dumps(r.json(), indent=4))
        logging.info("Schema is Updated")
        logging.info("I'll be back")
        os.execl(sys.executable, *([sys.executable] + sys.argv))

    def handle_input_message(self, client, msg, struct_topic):
        schema_dict = self.get_unit_schema()
        topic_type, topic_name = self.search_topic_in_schema(schema_dict, struct_topic[1])

        if topic_type == 'input_topic' and topic_name == 'input/pepeunit':
            print('Success load input state')
            value = msg.payload.decode()
            try:
                value = int(value)
                with open(f'tmp/test_units/{self.unit.uuid}/log.json', 'w') as f:
                    f.write(json.dumps({'value': value, 'input_topic': struct_topic}))
                for topic in schema_dict['output_topic'].keys():
                    self.pub_output_topic_by_name(client, 'output/pepeunit', str(value))
            except ValueError:
                pass

    async def publish(self):
        msg_count = 1
        schema_dict = self.get_unit_schema()
        while True:
            if (time.time() - self.settings.DELAY_PUB_MSG) >= self.settings.DELAY_PUB_MSG:
                for topic in schema_dict['output_topic'].keys():
                    msg = f"messages: {msg_count // 10}"
                    self.pub_output_topic_by_name(self.client, topic, msg)
                msg_count += 1

            if (time.time() - self.settings.STATE_SEND_INTERVAL) >= self.settings.STATE_SEND_INTERVAL:
                topic = schema_dict['output_base_topic']['state/pepeunit'][0]
                msg = self.get_unit_state()
                self.client.publish(topic, msg)
            await asyncio.sleep(1)

    def get_unit_state(self):
        memeory_info = psutil.virtual_memory()

        state_dict = {
            'millis': round(time.time() * 1000),
            'mem_free': memeory_info.available,
            'mem_alloc': memeory_info.total - memeory_info.available,
            'freq': psutil.cpu_freq().current,
            'commit_version': self.settings.COMMIT_VERSION,
        }
        return json.dumps(state_dict)

    def get_topic_split(self, topic):
        return tuple(topic.split('/'))

    def get_unit_schema(self):
        with open(f"tmp/test_units/{self.unit.uuid}/schema.json", 'r') as f:
            return json.loads(f.read())

    def get_input_topics(self) -> list[str]:
        schema_dict = self.get_unit_schema()

        input_topics = []
        for topic_type in schema_dict.keys():
            if topic_type.find('input') >= 0:
                for topic in schema_dict[topic_type].keys():
                    input_topics.extend(schema_dict[topic_type][topic])

        return input_topics

    def pub_output_topic_by_name(self, client, topic_name: str, message: str) -> None:
        schema_dict = self.get_unit_schema()

        if topic_name not in schema_dict['output_topic'].keys():
            raise KeyError('Not topic in schema')

        for topic in schema_dict['output_topic'][topic_name]:
            result = client.publish(topic, message)

            if result[0] == 0:
                print(f"Send `{message}` to topic `{topic}`")
            else:
                print(f"Failed to send message to topic {topic}")

    def search_topic_in_schema(self, schema_dict: dict, node_uuid: str) -> tuple[str, str]:

        for topic_type in schema_dict.keys():
            for topic_name in schema_dict[topic_type].keys():
                for topic in schema_dict[topic_type][topic_name]:
                    if topic.find(node_uuid) >= 0:
                        return (topic_type, topic_name)

        raise ValueError

    async def run(self):
        await self.connect_mqtt()
        self.client.loop_start()
        await self.publish()
        self.client.loop_stop()
