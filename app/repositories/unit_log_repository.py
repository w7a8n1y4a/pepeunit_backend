import uuid as uuid_pkg
from datetime import datetime, timedelta
from typing import Optional, Union

from clickhouse_driver import Client
from fastapi import Depends
from fastapi.params import Query

from app.configs.clickhouse import get_clickhouse_client
from app.dto.clickhouse.log import UnitLog
from app.dto.clickhouse.orm import ClickhouseOrm
from app.dto.enum import LogLevel, OrderByDate
from app.schemas.gql.inputs.unit import UnitLogFilterInput
from app.schemas.pydantic.unit import UnitLogFilter


class UnitLogRepository:
    client: Client

    def __init__(self, client: Client = Depends(get_clickhouse_client)) -> None:
        self.client = client
        self.orm = ClickhouseOrm(client)

    def create(self, unit_log: UnitLog) -> int:
        unit_log = self.orm.insert('unit_logs', [unit_log])
        return unit_log

    def bulk_create(self, unit_logs: list[UnitLog]) -> int:
        unit_logs = self.orm.insert('unit_logs', unit_logs)
        return unit_logs

    def get(self, uuid: uuid_pkg.UUID) -> Optional[UnitLog]:

        return self.orm.get(
            f"select {UnitLog.get_keys()} from unit_logs where uuid = %(uuid)s", {'uuid': uuid}, UnitLog
        )

    def delete(self, uuid: uuid_pkg.UUID) -> None:
        query = f"delete from unit_logs where unit_uuid = %(uuid)s"
        self.client.execute(query, {'uuid': uuid})

    def list(self, filters: Union[UnitLogFilter, UnitLogFilterInput]) -> tuple[int, list[UnitLog]]:

        query = f"select {UnitLog.get_keys()} from unit_logs where unit_uuid = %(uuid)s"
        count_query = f"select count() as count from unit_logs where unit_uuid = %(uuid)s"

        filters.level = [] if filters.level is None else filters.level

        if filters.level:
            filters.level = filters.level.default if isinstance(filters.level, Query) else filters.level
            data = ', '.join([f"'{item}'" for item in filters.level])
            level_append = f' AND level in ({data})'

            query += level_append
            count_query += level_append
        elif isinstance(filters.level, list) and not len(filters.level):
            level_append = f' AND level in (0)'

            query += level_append
            count_query += level_append

        count = self.client.execute(count_query, {'uuid': filters.uuid})

        if filters.order_by_create_date:
            query += f" order by create_datetime {filters.order_by_create_date.value}"

        if filters.limit:
            query += f" limit %(limit)s"

        if filters.offset:
            query += f" offset %(offset)s"

        unit_logs = self.orm.get_many(
            query,
            {
                'uuid': filters.uuid,
                'limit': filters.limit,
                'offset': filters.offset,
            },
            UnitLog,
        )

        return count[0][0], unit_logs
