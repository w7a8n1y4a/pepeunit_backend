from typing import Optional, TypeVar

from clickhouse_driver import Client
from pydantic import BaseModel

T = TypeVar('T')


class ClickhouseOrm:
    client: Client

    def __init__(self, client: Client) -> None:
        self.client = client

    def insert(self, table_name: str, data: list[BaseModel]) -> int:

        if len(data) == 0:
            return 0
        else:
            keys = data[0].model_fields.keys()

        unit_log = self.client.execute(
            f"INSERT INTO {table_name} ({', '.join(keys)}) VALUES", [item.to_dict() for item in data]
        )

        return unit_log

    def get(self, query: str, params: dict, result_model: type[T]) -> Optional[T]:
        data = self.client.execute(query, params, with_column_types=True)
        return result_model(**{name[0]: value for value, name in zip(data[0][0], data[-1])}) if len(data[0]) else None

    def get_many(self, query: str, params: dict, result_model: type[T]) -> list[T]:
        data = self.client.execute(query, params, with_column_types=True)
        columns = data[1]
        return (
            [result_model(**{name[0]: value for value, name in zip(item, columns)}) for item in data[0]]
            if len(data[0])
            else []
        )
