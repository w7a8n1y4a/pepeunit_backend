import asyncio
import json
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


class FileManager:
    @staticmethod
    def read_json_file(file_path: str) -> dict:
        with open(file_path, 'r') as f:
            return json.loads(f.read())

    @staticmethod
    def write_json_file(file_path: str, data: dict) -> None:
        with open(file_path, 'w') as f:
            f.write(json.dumps(data, indent=4))

    @staticmethod
    def prepare_update_directory(unit_uuid: str) -> str:
        new_version_path = f'tmp/test_units/{unit_uuid}/update'
        shutil.rmtree(new_version_path, ignore_errors=True)
        os.mkdir(new_version_path)
        return new_version_path

    @staticmethod
    def copy_update_files(source_path: str, destination_path: str) -> None:
        shutil.copytree(source_path, destination_path, dirs_exist_ok=True)

    @staticmethod
    def extract_archive(file_path: str, extract_path: str, archive_format: str) -> None:
        if archive_format == 'tgz':
            with open(file_path, 'rb') as f:
                producer = zlib.decompressobj(wbits=9)
                tar_data = producer.decompress(f.read()) + producer.flush()
                tar_filepath = f'{os.path.dirname(file_path)}/update.tar'
                with open(tar_filepath, 'wb') as tar_file:
                    tar_file.write(tar_data)
                shutil.unpack_archive(tar_filepath, extract_path, 'tar')
        else:
            shutil.unpack_archive(file_path, extract_path, archive_format)


class Downloader:
    @staticmethod
    async def download_file(url: str, file_path: str, headers: dict = None) -> None:
        async with httpx.AsyncClient() as client:
            r = await client.get(url=url, headers=headers)
            with open(file_path, 'wb') as f:
                f.write(r.content)


class UnitStateManager:
    @staticmethod
    def get_system_state(commit_version: str) -> dict:
        memory_info = psutil.virtual_memory()
        return {
            'millis': round(time.time() * 1000),
            'mem_free': memory_info.available,
            'mem_alloc': memory_info.total - memory_info.available,
            'freq': psutil.cpu_freq().current,
            'commit_version': commit_version,
        }


class SchemaManager:
    def __init__(self, unit_uuid: str):
        self.unit_uuid = unit_uuid

    def get_schema(self) -> dict:
        schema_data = FileManager.read_json_file(f"tmp/test_units/{self.unit_uuid}/schema.json")
        return json.loads(schema_data) if isinstance(schema_data, str) else schema_data

    def get_input_topics(self) -> list[str]:
        schema_dict = self.get_schema()
        input_topics = []
        for topic_type in schema_dict.keys():
            if 'input' in topic_type:
                for topic in schema_dict[topic_type].keys():
                    input_topics.extend(schema_dict[topic_type][topic])
        return input_topics

    def search_topic_in_schema(self, node_uuid: str) -> tuple[str, str]:
        schema_dict = self.get_schema()
        for topic_type in schema_dict.keys():
            for topic_name in schema_dict[topic_type].keys():
                for topic in schema_dict[topic_type][topic_name]:
                    if node_uuid in topic:
                        return topic_type, topic_name
        raise ValueError(f"Topic with node_uuid {node_uuid} not found in schema")


class MQTTMessageHandler:
    def __init__(self, mqtt_client: 'MQTTClient'):
        self.mqtt_client = mqtt_client

    def handle_message(self, client, userdata, msg) -> None:
        struct_topic = self.mqtt_client.get_topic_split(msg.topic)

        if len(struct_topic) == 5:
            self._handle_structured_message(client, msg, struct_topic)
        elif len(struct_topic) == 3:
            self._handle_input_message(client, msg, struct_topic)

    def _handle_structured_message(self, client, msg, struct_topic) -> None:
        _, destination, unit_uuid, topic_name, *_ = struct_topic

        if destination == 'input_base_topic':
            if topic_name == 'update':
                self._handle_update(msg)
            elif topic_name == 'schema_update':
                self._handle_schema_update(client)

    def _handle_update(self, msg) -> None:
        update_dict = json.loads(msg.payload.decode())
        new_version = update_dict['NEW_COMMIT_VERSION']

        new_version_path = FileManager.prepare_update_directory(self.mqtt_client.unit.uuid)

        if 'COMPILED_FIRMWARE_LINK' in update_dict:
            self._download_and_process_update(update_dict['COMPILED_FIRMWARE_LINK'], new_version_path, 'zip')

        if self.mqtt_client.settings.COMMIT_VERSION != new_version:
            self._download_and_process_update(
                self._get_pepeunit_firmware_url(), new_version_path, 'tgz', self._get_auth_headers()
            )

        FileManager.copy_update_files(new_version_path, f'tmp/test_units/{self.mqtt_client.unit.uuid}')
        self.mqtt_client.settings = self.mqtt_client.get_settings()

    def _download_and_process_update(
        self, url: str, extract_path: str, archive_format: str, headers: dict = None
    ) -> None:
        file_path = f'tmp/test_units/{self.mqtt_client.unit.uuid}/update.{archive_format}'
        asyncio.run(Downloader.download_file(url, file_path, headers))
        FileManager.extract_archive(file_path, extract_path, archive_format)

    def _get_pepeunit_firmware_url(self) -> str:
        wbits = 9
        level = 9
        return (
            f"{self.mqtt_client.settings.HTTP_TYPE}://{self.mqtt_client.settings.PEPEUNIT_URL}"
            f"{self.mqtt_client.settings.PEPEUNIT_APP_PREFIX}"
            f"{self.mqtt_client.settings.PEPEUNIT_API_ACTUAL_PREFIX}/units/firmware/tgz/{self.mqtt_client.unit.uuid}"
            f"?wbits={wbits}&level={level}"
        )

    def _get_auth_headers(self) -> dict:
        return {'accept': 'application/json', 'x-auth-token': self.mqtt_client.settings.PEPEUNIT_TOKEN.encode()}

    def _handle_schema_update(self, client) -> None:
        headers = self._get_auth_headers()
        url = (
            f"{self.mqtt_client.settings.HTTP_TYPE}://{self.mqtt_client.settings.PEPEUNIT_URL}"
            f"{self.mqtt_client.settings.PEPEUNIT_APP_PREFIX}"
            f"{self.mqtt_client.settings.PEPEUNIT_API_ACTUAL_PREFIX}/units/get_current_schema/{self.mqtt_client.unit.uuid}"
        )

        async def update_schema():
            async with httpx.AsyncClient() as http_client:
                r = await http_client.get(url=url, headers=headers)
                FileManager.write_json_file(f'tmp/test_units/{self.mqtt_client.unit.uuid}/schema.json', r.json())
                client.subscribe([(topic, 0) for topic in self.mqtt_client.schema_manager.get_input_topics()])

        asyncio.run(update_schema())

    def _handle_input_message(self, client, msg, struct_topic) -> None:
        try:
            topic_type, topic_name = self.mqtt_client.schema_manager.search_topic_in_schema(struct_topic[1])

            if topic_type == 'input_topic' and topic_name == 'input/pepeunit':
                value = msg.payload.decode()
                try:
                    value = int(value)
                    FileManager.write_json_file(
                        f'tmp/test_units/{self.mqtt_client.unit.uuid}/log.json',
                        {'value': value, 'input_topic': struct_topic},
                    )
                    self.mqtt_client.publish_to_output_topic('output/pepeunit', str(value))
                except ValueError:
                    pass
        except ValueError:
            pass


class MQTTClient:
    def __init__(self, unit):
        self.client = None
        self.unit = unit
        self.settings = self.get_settings()
        self.schema_manager = SchemaManager(self.unit.uuid)
        self.message_handler = MQTTMessageHandler(self)

    def get_settings(self) -> BaseConfig:
        return BaseConfig(**FileManager.read_json_file(f"tmp/test_units/{self.unit.uuid}/env.json"))

    async def connect_mqtt(self) -> mqtt_client.Client:
        self.client = mqtt_client.Client(mqtt_client.CallbackAPIVersion.VERSION1, str(uuid.uuid4()))

        self.client.username_pw_set(self.settings.PEPEUNIT_TOKEN, '')
        self.client.on_connect = self.on_connect
        self.client.on_subscribe = self.on_subscribe
        self.client.on_message = self.message_handler.handle_message

        self.client.connect(self.settings.MQTT_URL, self.settings.MQTT_PORT)
        return self.client

    def on_connect(self, client, userdata, flags, rc) -> None:
        if rc == 0:
            print("Connected to MQTT Broker!")
        else:
            print(f"Failed to connect, return code {rc}\n")

        client.subscribe([(topic, 0) for topic in self.schema_manager.get_input_topics()])

    def on_subscribe(self, client, userdata, mid, granted_qos) -> None:
        print("Subscribed: " + str(mid) + " " + str(granted_qos))

    async def publish_messages(self) -> None:
        msg_count = 1
        schema_dict = self.schema_manager.get_schema()

        while True:
            current_time = time.time()

            if (current_time - self.settings.DELAY_PUB_MSG) >= self.settings.DELAY_PUB_MSG:
                for topic in schema_dict['output_topic'].keys():
                    msg = f"messages: {msg_count // 10}"
                    self.publish_to_output_topic(topic, msg)
                msg_count += 1

            if (current_time - self.settings.STATE_SEND_INTERVAL) >= self.settings.STATE_SEND_INTERVAL:
                topic = schema_dict['output_base_topic']['state/pepeunit'][0]
                msg = json.dumps(UnitStateManager.get_system_state(self.settings.COMMIT_VERSION))
                self.client.publish(topic, msg)

            await asyncio.sleep(0.25)

    def publish_to_output_topic(self, topic_name: str, message: str) -> None:
        schema_dict = self.schema_manager.get_schema()

        if topic_name not in schema_dict['output_topic']:
            raise KeyError(f'Topic {topic_name} not found in schema')

        for topic in schema_dict['output_topic'][topic_name]:
            result = self.client.publish(topic, message)
            if result[0] != 0:
                print(f"Failed to send message to topic {topic}")

    @staticmethod
    def get_topic_split(topic: str) -> tuple:
        return tuple(topic.split('/'))

    async def run(self) -> None:
        await self.connect_mqtt()
        self.client.loop_start()
        await self.publish_messages()
        self.client.loop_stop()
