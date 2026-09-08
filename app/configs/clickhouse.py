from contextlib import contextmanager

from clickhouse_driver import Client

from app import settings


def _make_client() -> Client:
    return Client(
        host=settings.pu_clickhouse_connection.host,
        port=settings.pu_clickhouse_connection.port,
        user=settings.pu_clickhouse_connection.user,
        password=settings.pu_clickhouse_connection.password,
        database=settings.pu_clickhouse_connection.database,
        connect_timeout=settings.pu_http_connect_timeout,
    )


def get_clickhouse_client():
    client = _make_client()
    try:
        yield client
    finally:
        client.disconnect()


@contextmanager
def get_hand_clickhouse_client():
    client = _make_client()
    try:
        yield client
    finally:
        client.disconnect()
