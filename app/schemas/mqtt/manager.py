import asyncio
import concurrent.futures
import json
import logging
import time

from fastapi_mqtt import FastMQTT, MQTTConfig

from app import settings
from app.configs.errors import MqttError
from app.configs.utils import acquire_file_lock
from app.dto.agent.abc import AgentBackend
from app.dto.enum import GlobalPrefixTopic


class MqttManager:
    def __init__(self) -> None:
        mqtt_config = MQTTConfig(
            host=settings.pu_mqtt_host,
            port=settings.pu_mqtt_port,
            keepalive=settings.pu_mqtt_keepalive,
            username=AgentBackend(
                name=settings.pu_domain
            ).generate_agent_token(),
            password="",
            reconnect_retries=-1,
            reconnect_delay=6,
        )
        self.mqtt = FastMQTT(config=mqtt_config)

        self._loop: asyncio.AbstractEventLoop | None = None
        self._connected: bool = False
        self._watchdog_task: asyncio.Task | None = None
        self._last_resubscribe_monotonic: float = 0.0
        self._subscription_lock_fd = None

    def attach_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def get_loop(self) -> asyncio.AbstractEventLoop | None:
        return self._loop

    def is_connected(self) -> bool:
        return (
            bool(getattr(self.mqtt.client, "is_connected", False))
            or self._connected
        )

    def on_connect(self, client, _flags, _rc, _properties) -> None:
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            logging.error(
                "MQTT on_connect called without running asyncio loop"
            )
            return
        self._connected = True

        async def _subscribe_after_connect() -> None:
            lock_fd = self._subscription_lock_fd or acquire_file_lock(
                "tmp/mqtt_subscribe.lock"
            )
            await asyncio.sleep(2)
            if not lock_fd:
                logging.info(
                    "Another worker already subscribed to MQTT topics"
                )
                return

            self._subscription_lock_fd = lock_fd
            logging.info("MQTT subscriptions initialized in this worker")
            try:
                client.subscribe(
                    f"{settings.pu_domain}/+/+/+{GlobalPrefixTopic.BACKEND_SUB_PREFIX.value}"
                )
                self._last_resubscribe_monotonic = time.monotonic()
            except Exception:
                try:
                    lock_fd.close()
                finally:
                    self._subscription_lock_fd = None
                raise

        loop = self._loop
        loop.create_task(_subscribe_after_connect())
        if self._watchdog_task is None or self._watchdog_task.done():
            self._watchdog_task = loop.create_task(self._watchdog())

    def on_disconnect(self, _client, _packet) -> None:
        self._connected = False
        logging.info(
            "Disconnected from MQTT server: %s:%s",
            settings.pu_mqtt_host,
            settings.pu_mqtt_port,
        )

    async def _watchdog(self) -> None:
        interval = 5
        timeout = 20
        resubscribe_interval = 120

        while True:
            await asyncio.sleep(interval)
            try:
                gmqtt_client = self.mqtt.client
                conn = getattr(gmqtt_client, "_connection", None)
                if conn is None or conn.is_closing():
                    continue

                now = time.monotonic()
                last_in = getattr(conn, "_last_data_in", None)
                last_out = getattr(conn, "_last_data_out", None)

                if (
                    self._subscription_lock_fd is not None
                    and (now - self._last_resubscribe_monotonic)
                    >= resubscribe_interval
                ):
                    try:
                        gmqtt_client.subscribe(
                            f"{settings.pu_domain}/+/+/+{GlobalPrefixTopic.BACKEND_SUB_PREFIX.value}"
                        )
                        self._last_resubscribe_monotonic = now
                    except Exception as e:
                        logging.warning(
                            f"MQTT watchdog resubscribe failed: {e}"
                        )

                if last_out is not None and (now - last_out) >= interval:
                    try:
                        conn._send_ping_request()
                    except Exception as e:
                        logging.warning(f"MQTT watchdog ping failed: {e}")

                if last_in is not None and (now - last_in) >= timeout:
                    logging.warning(
                        "MQTT watchdog: no inbound data for %ss, closing connection to trigger reconnect",
                        timeout,
                    )
                    await conn.close()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logging.error(f"MQTT watchdog error: {e}")

    def publish(self, topic: str, msg: dict | str) -> None:
        payload = json.dumps(msg) if isinstance(msg, dict) else msg

        if self._loop is None:
            msg = f"Error when publish message to topic {topic}: MQTT loop is not initialized"
            raise MqttError(msg)

        if not self.is_connected():
            msg = f"Error when publish message to topic {topic}: MQTT client is disconnected"
            raise MqttError(msg)

        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None

        if running_loop is self._loop:
            self.mqtt.publish(topic, payload)
            return

        fut: concurrent.futures.Future[None] = concurrent.futures.Future()

        def _do_publish() -> None:
            try:
                self.mqtt.publish(topic, payload)
                fut.set_result(None)
            except Exception as e:
                fut.set_exception(e)

        self._loop.call_soon_threadsafe(_do_publish)
        try:
            fut.result(timeout=5)
        except concurrent.futures.TimeoutError as err:
            msg = f"Error when publish message to topic {topic}: publish timed out (MQTT loop busy or stopped)"
            raise MqttError(msg) from err
        except Exception as err:
            msg = f"Error when publish message to topic {topic}: {err}"
            raise MqttError(msg) from err


mqtt_manager = MqttManager()
