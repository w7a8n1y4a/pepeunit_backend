import json

from app.configs.errors import MqttError
from app.repositories.enum import ReservedStateKey
from app.schemas.pydantic.unit import UnitStateRead


def get_topic_split(topic: str) -> tuple[str, ...]:
    return tuple(topic.split('/'))


def get_only_reserved_keys(input_dict: dict) -> dict:
    reserved_keys = {key.value for key in ReservedStateKey}
    filtered_dict = {key: value for key, value in input_dict.items() if key in reserved_keys}
    return UnitStateRead(**filtered_dict).dict()


def publish_to_topic(topic: str, msg: dict or str) -> None:
    from app.schemas.mqtt.topic import mqtt

    try:
        mqtt.publish(topic, json.dumps(msg) if isinstance(msg, dict) else msg)
    except AttributeError:
        raise MqttError('Error when publish message to topic {}: {}'.format(topic, 'Backend MQTT session is invalid'))
    except Exception as ex:
        raise MqttError('Error when publish message to topic {}: {}'.format(topic, ex))
