import json
import logging

from app.configs.errors import app_errors


def get_topic_split(topic: str) -> tuple[str, ...]:
    return tuple(topic.split('/'))


def publish_to_topic(topic: str, msg: dict or str) -> None:
    from app.schemas.mqtt.topic import mqtt

    try:
        mqtt.publish(topic, json.dumps(msg) if isinstance(msg, dict) else msg)
    except AttributeError:
        app_errors.mqtt_error.raise_exception(
            'Error when publish message to topic {}: {}'.format(topic, 'Backend MQTT session is invalid')
        )
    except Exception as ex:
        app_errors.mqtt_error.raise_exception('Error when publish message to topic {}: {}'.format(topic, ex))
