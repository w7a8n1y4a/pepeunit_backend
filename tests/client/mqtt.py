import asyncio
import datetime
import enum
import json
import os
import shutil
import sys
import time
import uuid
import zlib
from collections import namedtuple

import httpx
import psutil
from paho.mqtt import client as paho_mqtt_client


class Settings:
    PEPEUNIT_URL = ''
    PEPEUNIT_APP_PREFIX = ''
    PEPEUNIT_API_ACTUAL_PREFIX = ''
    HTTP_TYPE = ''
    MQTT_URL = ''
    MQTT_PORT = 1883
    PEPEUNIT_TOKEN = ''
    SYNC_ENCRYPT_KEY = ''
    SECRET_KEY = ''
    COMMIT_VERSION = ''
    PING_INTERVAL = 30
    STATE_SEND_INTERVAL = 300
    DELAY_PUB_MSG = 1
    PUBLISH_LOG_LEVEL = 'Debug'

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class LogLevel(enum.Enum):
    DEBUG = 'Debug'
    INFO = 'Info'
    WARNING = 'Warning'
    ERROR = 'Error'
    CRITICAL = 'Critical'

    def get_int_level(self) -> int:
        level_mapping = {
            LogLevel.DEBUG: 0,
            LogLevel.INFO: 1,
            LogLevel.WARNING: 2,
            LogLevel.ERROR: 3,
            LogLevel.CRITICAL: 4,
        }
        return level_mapping[self]


class DualLogger:
    def __init__(self, mqtt_client: 'MQTTClient', publish_level: LogLevel, unit_uuid: str):
        self.unit_uuid = unit_uuid
        self.mqtt_client = mqtt_client
        self.publish_level = publish_level
        self.log_file = f'tmp/test_units/{self.unit_uuid}/log.json'

    def log(self, level: LogLevel, message: str, client: paho_mqtt_client.Client = None):

        log_entry = {'level': level.value, 'text': message, 'create_datetime': datetime.datetime.utcnow().isoformat()}

        self._write_to_file(log_entry)

        if client and level.get_int_level() >= self.publish_level.get_int_level():
            self._send_mqtt(client, log_entry)

    def _write_to_file(self, log_entry):

        try:
            if not os.path.exists(self.log_file):
                with open(self.log_file, 'w') as f:
                    f.write(json.dumps([]))

            with open(self.log_file, 'r') as f:
                logs = json.loads(f.read())

            logs.append(log_entry)

            with open(self.log_file, 'w') as f:
                f.write(json.dumps(logs, indent=4))

        except Exception as e:
            print(f"Ошибка записи в файлы при сохранении в log.json: {e}")

    def _send_mqtt(self, client, log_entry):
        try:
            topic = self.mqtt_client.unit_file_manager.schema['output_base_topic']['log/pepeunit'][0]
            client.publish(topic, json.dumps(log_entry))
        except Exception as e:
            print(f"Ошибка при отправке в MQTT: {e}")


class FileManager:
    @staticmethod
    def read_json_file(file_path: str) -> dict or list:
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


class UnitFileManager(FileManager):

    def __init__(self, unit_uuid: str):
        self.unit_uuid = unit_uuid
        self.schema = self.read_json_file(f'tmp/test_units/{self.unit_uuid}/schema.json')
        self.settings = Settings(**FileManager.read_json_file(f"tmp/test_units/{self.unit_uuid}/env.json"))

    def update_schema(self, schema_dict: dict) -> None:
        self.schema = schema_dict
        self.write_json_file(f'tmp/test_units/{self.unit_uuid}/schema.json', schema_dict)

    def update_env(self, env_dict: dict) -> None:
        self.settings = Settings(**env_dict)
        self.write_json_file(f'tmp/test_units/{self.unit_uuid}/env.json', env_dict)

    def update_env_from_file(self) -> None:
        self.settings = Settings(**FileManager.read_json_file(f"tmp/test_units/{self.unit_uuid}/env.json"))

    def get_input_topics(self) -> list[str]:
        input_topics = []
        for topic_type in self.schema.keys():
            if 'input' in topic_type:
                for topic in self.schema[topic_type].keys():
                    input_topics.extend(self.schema[topic_type][topic])
        return input_topics

    def search_topic_in_schema(self, node_uuid: str) -> tuple[str, str]:
        for topic_type in self.schema.keys():
            for topic_name in self.schema[topic_type].keys():
                for topic in self.schema[topic_type][topic_name]:
                    if node_uuid in topic:
                        return topic_type, topic_name
        raise ValueError(f"Topic with node_uuid {node_uuid} not found in schema")

    def get_log_file(self) -> list:
        return self.read_json_file(f'tmp/test_units/{self.unit_uuid}/log.json')


class MQTTMessageHandler:
    def __init__(self, mqtt_client: 'MQTTClient'):
        self.mqtt_client = mqtt_client

    def handle_message(self, client, userdata, msg) -> None:
        struct_topic = self.mqtt_client.get_topic_split(msg.topic)

        if len(struct_topic) == 5:
            self._handle_structured_message(client, msg, struct_topic)
        elif len(struct_topic) == 2:
            self._handle_input_message(client, msg, struct_topic)

    @staticmethod
    async def download_file(url: str, file_path: str, headers: dict = None) -> None:
        async with httpx.AsyncClient() as client:
            r = await client.get(url=url, headers=headers)
            with open(file_path, 'wb') as f:
                f.write(r.content)

    def _handle_structured_message(self, client, msg, struct_topic) -> None:
        _, destination, unit_uuid, topic_name, *_ = struct_topic

        if destination == 'input_base_topic':

            self.mqtt_client.dual_logger.log(LogLevel.INFO, f'Unit {unit_uuid} get msg from topic {topic_name}', client)

            if topic_name == 'update':
                self._handle_update(msg)
            elif topic_name == 'env_update':
                self._handle_env_update()
            elif topic_name == 'schema_update':
                self._handle_schema_update(client)
            elif topic_name == 'log_sync':
                self._handle_log_sync(client)

    def _handle_update(self, msg) -> None:
        update_dict = json.loads(msg.payload.decode())
        new_version = update_dict['NEW_COMMIT_VERSION']

        new_version_path = FileManager.prepare_update_directory(self.mqtt_client.unit.uuid)

        if 'COMPILED_FIRMWARE_LINK' in update_dict:
            self._download_and_process_update(update_dict['COMPILED_FIRMWARE_LINK'], new_version_path, 'zip')

        if self.mqtt_client.unit_file_manager.settings.COMMIT_VERSION != new_version:
            self._download_and_process_update(
                self._get_pepeunit_firmware_url(), new_version_path, 'tgz', self._get_auth_headers()
            )

        FileManager.copy_update_files(new_version_path, f'tmp/test_units/{self.mqtt_client.unit.uuid}')
        self.mqtt_client.unit_file_manager.update_env_from_file()

    def _download_and_process_update(
        self, url: str, extract_path: str, archive_format: str, headers: dict = None
    ) -> None:
        file_path = f'tmp/test_units/{self.mqtt_client.unit.uuid}/update.{archive_format}'
        asyncio.run(self.download_file(url, file_path, headers))
        FileManager.extract_archive(file_path, extract_path, archive_format)

    def _get_pepeunit_firmware_url(self) -> str:
        wbits = 9
        level = 9
        return (
            f"{self.mqtt_client.unit_file_manager.settings.HTTP_TYPE}://{self.mqtt_client.unit_file_manager.settings.PEPEUNIT_URL}"
            f"{self.mqtt_client.unit_file_manager.settings.PEPEUNIT_APP_PREFIX}"
            f"{self.mqtt_client.unit_file_manager.settings.PEPEUNIT_API_ACTUAL_PREFIX}/units/firmware/tgz/{self.mqtt_client.unit.uuid}"
            f"?wbits={wbits}&level={level}"
        )

    def _get_auth_headers(self) -> dict:
        return {
            'accept': 'application/json',
            'x-auth-token': self.mqtt_client.unit_file_manager.settings.PEPEUNIT_TOKEN.encode(),
        }

    def _handle_schema_update(self, client) -> None:
        headers = self._get_auth_headers()
        url = (
            f"{self.mqtt_client.unit_file_manager.settings.HTTP_TYPE}://{self.mqtt_client.unit_file_manager.settings.PEPEUNIT_URL}"
            f"{self.mqtt_client.unit_file_manager.settings.PEPEUNIT_APP_PREFIX}"
            f"{self.mqtt_client.unit_file_manager.settings.PEPEUNIT_API_ACTUAL_PREFIX}/units/get_current_schema/{self.mqtt_client.unit.uuid}"
        )

        result = httpx.get(url, headers=headers)
        self.mqtt_client.unit_file_manager.update_schema(json.loads(result.json()))
        client.subscribe([(topic, 0) for topic in self.mqtt_client.unit_file_manager.get_input_topics()])

    def _handle_env_update(self) -> None:
        headers = self._get_auth_headers()
        url = (
            f"{self.mqtt_client.unit_file_manager.settings.HTTP_TYPE}://{self.mqtt_client.unit_file_manager.settings.PEPEUNIT_URL}"
            f"{self.mqtt_client.unit_file_manager.settings.PEPEUNIT_APP_PREFIX}"
            f"{self.mqtt_client.unit_file_manager.settings.PEPEUNIT_API_ACTUAL_PREFIX}/units/env/{self.mqtt_client.unit.uuid}"
        )

        result = httpx.get(url, headers=headers)
        self.mqtt_client.unit_file_manager.update_env(json.loads(result.json()))

    def _handle_log_sync(self, client) -> None:
        topic = self.mqtt_client.unit_file_manager.schema['output_base_topic']['log/pepeunit'][0]

        try:
            msg = json.dumps(self.mqtt_client.unit_file_manager.get_log_file(), indent=4)
        except Exception as e:
            msg = json.dumps({'level': 'Debug', 'message': str(e)})

        client.publish(topic, msg)

    def _handle_input_message(self, client, msg, struct_topic) -> None:
        try:
            topic_type, topic_name = self.mqtt_client.unit_file_manager.search_topic_in_schema(struct_topic[1])

            if topic_type == 'input_topic' and topic_name == 'input':
                value = msg.payload.decode()
                try:
                    value = int(value)
                    if value == 0:
                        FileManager.write_json_file(
                            f'tmp/test_units/{self.mqtt_client.unit.uuid}/log_state.json',
                            {'value': value, 'input_topic': struct_topic},
                        )
                        self.mqtt_client.publish_to_output_topic('output', str(value))
                except ValueError:
                    pass
        except ValueError:
            pass


class MQTTClient:
    def __init__(self, unit):
        self.client = None
        self.unit = unit
        self.unit_file_manager = UnitFileManager(unit_uuid=unit.uuid)
        self.dual_logger = DualLogger(self, LogLevel(self.unit_file_manager.settings.PUBLISH_LOG_LEVEL), self.unit.uuid)
        self.message_handler = MQTTMessageHandler(self)

    async def connect_mqtt(self) -> paho_mqtt_client.Client:
        self.client = paho_mqtt_client.Client(paho_mqtt_client.CallbackAPIVersion.VERSION1, str(uuid.uuid4()))

        self.client.username_pw_set(self.unit_file_manager.settings.PEPEUNIT_TOKEN, '')
        self.client.on_connect = self.on_connect
        self.client.on_subscribe = self.on_subscribe
        self.client.on_message = self.message_handler.handle_message

        self.client.connect(self.unit_file_manager.settings.MQTT_URL, self.unit_file_manager.settings.MQTT_PORT)
        return self.client

    def on_connect(self, client, userdata, flags, rc) -> None:
        if rc == 0:
            print("Connected to MQTT Broker!")
            self.dual_logger.log(LogLevel.INFO, 'Connected to MQTT Broker!', client)
        else:
            self.dual_logger.log(LogLevel.CRITICAL, f"Failed to connect, return code {rc}\n")

        client.subscribe([(topic, 0) for topic in self.unit_file_manager.get_input_topics()])

    def on_subscribe(self, client, userdata, mid, granted_qos) -> None:
        print("Subscribed: " + str(mid) + " " + str(granted_qos))
        self.dual_logger.log(LogLevel.INFO, "Subscribed: " + str(mid) + " " + str(granted_qos), client)

    def get_system_state(self) -> dict:
        memory_info = psutil.virtual_memory()
        return {
            'millis': round(time.time() * 1000),
            'mem_free': memory_info.available,
            'mem_alloc': memory_info.total - memory_info.available,
            'freq': psutil.cpu_freq().current,
            'commit_version': self.unit_file_manager.settings.COMMIT_VERSION,
        }

    async def publish_messages(self) -> None:
        msg_count = 1
        while True:
            current_time = time.time()

            if (
                current_time - self.unit_file_manager.settings.DELAY_PUB_MSG
            ) >= self.unit_file_manager.settings.DELAY_PUB_MSG:
                for topic in self.unit_file_manager.schema['output_topic'].keys():
                    msg = f"{msg_count // 10}"
                    self.publish_to_output_topic(topic, msg)
                msg_count += 1

            if (
                current_time - self.unit_file_manager.settings.STATE_SEND_INTERVAL
            ) >= self.unit_file_manager.settings.STATE_SEND_INTERVAL:
                topic = self.unit_file_manager.schema['output_base_topic']['state/pepeunit'][0]
                msg = json.dumps(self.get_system_state())
                self.client.publish(topic, msg)

            await asyncio.sleep(0.25)

    def publish_to_output_topic(self, topic_name: str, message: str) -> None:
        if topic_name not in self.unit_file_manager.schema['output_topic']:
            self.dual_logger.log(LogLevel.CRITICAL, f'Topic {topic_name} not found in schema')
            raise KeyError(f'Topic {topic_name} not found in schema')

        for topic in self.unit_file_manager.schema['output_topic'][topic_name]:
            result = self.client.publish(topic, message)
            if result[0] != 0:
                self.dual_logger.log(LogLevel.ERROR, f"Failed to send message to topic {topic}", self.client)

    @staticmethod
    def get_topic_split(topic: str) -> tuple:
        return tuple(topic.split('/'))

    async def run(self) -> None:
        try:
            await self.connect_mqtt()
            self.client.loop_start()
            await self.publish_messages()
            self.client.loop_stop()
        except Exception as e:
            self.dual_logger.log(LogLevel.CRITICAL, f'Exception: {e}')


if __name__ == '__main__':
    UnitType = namedtuple('Unit', ['uuid'])
    test_unit = UnitType(uuid='619f8c6e-4afd-4d3d-bc62-338d666fcc28')

    mqtt_client = MQTTClient(test_unit)
    asyncio.run(mqtt_client.run())
