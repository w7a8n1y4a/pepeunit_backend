from app.schemas.mqtt.handler import MqttMessageHandler
from app.schemas.mqtt.manager import mqtt_manager

mqtt = mqtt_manager.mqtt
message_handler = MqttMessageHandler()


@mqtt.on_connect()
def connect(client, _flags, _rc, _properties):
    mqtt_manager.on_connect(client, _flags, _rc, _properties)


@mqtt.on_message()
async def message_to_topic(_client, topic, payload, _qos, _properties):
    await message_handler.handle(topic, payload)


@mqtt.on_disconnect()
def disconnect(client, _packet):
    mqtt_manager.on_disconnect(client, _packet)
