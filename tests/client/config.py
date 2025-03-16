import json


class BaseConfig:
    """Config variables"""

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
    DELAY_PUB_MSG = 1
    PING_INTERVAL = 30
    STATE_SEND_INTERVAL = 300

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
