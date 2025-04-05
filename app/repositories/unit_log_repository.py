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

    def list(self, filters: Union[UnitLogFilter, UnitLogFilterInput]) -> tuple[int, list[UnitLog]]:

        query = f"select {UnitLog.get_keys()} from unit_logs where unit_uuid = %(uuid)s"

        if filters.level:
            filters.level = filters.level.default if isinstance(filters.level, Query) else filters.level
            data = ', '.join([f"'{item}'" for item in filters.level])
            query += f' AND level in ({data})'

        if filters.order_by_create_date:
            query += f" order by create_datetime {filters.order_by_create_date.value}"

        if filters.limit:
            query += f" limit %(limit)s"

        if filters.offset:
            query += f" offset %(offset)s"

        print(query)

        unit_logs = self.orm.get_many(
            query,
            {
                'uuid': filters.uuid,
                'limit': filters.limit,
                'offset': filters.offset,
            },
            UnitLog,
        )

        return len(unit_logs), unit_logs


if __name__ == '__main__':

    test = UnitLogRepository(next(get_clickhouse_client()))

    two = test.create(
        UnitLog(
            uuid=uuid_pkg.uuid4(),
            level=LogLevel.INFO,
            unit_uuid=uuid_pkg.uuid4(),
            text='test data',
            create_datetime=datetime.utcnow(),
        )
    )

    print(two)

    unit_uuid = uuid_pkg.uuid4()

    two = test.bulk_create(
        [
            UnitLog(
                uuid=uuid_pkg.uuid4(),
                level=LogLevel.INFO,
                unit_uuid=unit_uuid,
                text='test data',
                create_datetime=datetime.utcnow() - timedelta(hours=23, minutes=item),
            )
            for item in range(20)
        ]
    )

    print(two)

    print(test.get(uuid='46aac02a-747c-4d61-b9be-4f9c823c2a91'))

    data = test.list(
        UnitLogFilter(uuid=unit_uuid, order_by_create_date=OrderByDate.desc, level=[LogLevel.DEBUG], limit=10, offset=1)
    )

    print(data)

    for item in data[1]:
        print(item.create_datetime)
