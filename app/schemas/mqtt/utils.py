from app.configs.errors import MqttError
from app.dto.enum import ReservedStateKey
from app.schemas.mqtt.manager import mqtt_manager
from app.schemas.pydantic.unit import UnitStateRead


def get_topic_split(topic: str) -> tuple[str, ...]:
    return tuple(topic.split("/"))


def get_only_reserved_keys(input_dict: dict) -> dict:
    reserved_keys = {key.value for key in ReservedStateKey}
    filtered_dict = {
        key: value for key, value in input_dict.items() if key in reserved_keys
    }
    return UnitStateRead(**filtered_dict).dict()


def publish_to_topic(topic: str, msg: dict or str) -> None:
    try:
        mqtt_manager.publish(topic, msg)
    except MqttError as err:
        raise err
    except AttributeError as err:
        msg = "Error when publish message to topic {}: {}".format(
            topic, "Backend MQTT session is invalid"
        )
        raise MqttError(msg) from err
    except Exception as err:
        msg = f"Error when publish message to topic {topic}: {err}"
        raise MqttError(msg) from err
