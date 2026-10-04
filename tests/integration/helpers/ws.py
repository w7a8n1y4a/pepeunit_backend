import json
import socket
import ssl
import time
from contextlib import suppress
from urllib.parse import urlsplit

from wsproto import ConnectionType, WSConnection
from wsproto.events import (
    AcceptConnection,
    CloseConnection,
    Ping,
    RejectConnection,
    Request,
    TextMessage,
)

from app import settings


class NotificationSocket:
    """Blocking client of the notification socket against the running backend.

    wsproto ships with uvicorn, so no extra test dependency is needed.
    """

    def __init__(self, token: str | None, timeout: float = 10) -> None:
        url = urlsplit(settings.pu_link_prefix_and_v1)
        host = url.hostname
        port = url.port or (443 if url.scheme == "https" else 80)

        sock = socket.create_connection((host, port), timeout=timeout)
        if url.scheme == "https":
            sock = ssl.create_default_context().wrap_socket(
                sock, server_hostname=host
            )
        self.sock = sock
        self.ws = WSConnection(ConnectionType.CLIENT)
        self.accepted: bool | None = None
        self.close_code: int | None = None
        self._text = ""

        target = f"{url.path}/notifications/ws"
        if token:
            target += f"?x-auth-token={token}"
        self._send(self.ws.send(Request(host=host, target=target)))
        self._wait(lambda: self.accepted is not None, timeout)

    def recv_json(self, timeout: float = 10) -> dict | None:
        """Next message, None when the server closed the socket"""
        received: list[dict] = []

        def ready() -> bool:
            return bool(received) or self.close_code is not None

        self._wait(ready, timeout, on_message=received.append)
        return received[0] if received else None

    def close(self) -> None:
        with suppress(Exception):
            if self.close_code is None:
                self._send(self.ws.send(CloseConnection(code=1000)))
        self.sock.close()

    def _send(self, data: bytes) -> None:
        if data:
            self.sock.sendall(data)

    def _wait(self, done, timeout: float, on_message=None) -> None:
        deadline = time.monotonic() + timeout
        while not done():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                msg = "notification socket timed out"
                raise TimeoutError(msg)
            self.sock.settimeout(remaining)
            try:
                data = self.sock.recv(65536)
            except TimeoutError:
                continue
            if not data:
                self.close_code = self.close_code or 1006
                return
            self.ws.receive_data(data)
            for event in self.ws.events():
                self._handle(event, on_message)

    def _handle(self, event, on_message) -> None:
        if isinstance(event, AcceptConnection):
            self.accepted = True
        elif isinstance(event, RejectConnection):
            self.accepted = False
        elif isinstance(event, Ping):
            self._send(self.ws.send(event.response()))
        elif isinstance(event, TextMessage):
            self._text += event.data
            if event.message_finished:
                text, self._text = self._text, ""
                if on_message:
                    on_message(json.loads(text))
        elif isinstance(event, CloseConnection):
            self.close_code = event.code
            with suppress(Exception):
                self._send(self.ws.send(event.response()))
