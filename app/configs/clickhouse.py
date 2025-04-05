from clickhouse_driver import Client

from app import settings


def get_clickhouse_client():
    client = Client(
        host=settings.clickhouse_connection.host,
        port=settings.clickhouse_connection.port,
        user=settings.clickhouse_connection.user,
        password=settings.clickhouse_connection.password,
        database=settings.clickhouse_connection.database,
    )
    try:
        yield client
    finally:
        client.disconnect()
