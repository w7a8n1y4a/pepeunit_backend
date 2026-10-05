import enum
import uuid as uuid_pkg
from datetime import UTC, datetime

from clickhouse_driver import Client
from fastapi import Depends
from fastapi.params import Query

from app.configs.clickhouse import get_clickhouse_client
from app.dto.clickhouse.log import UnitErrorCount, UnitLog, UnitLogAggregate
from app.dto.clickhouse.orm import ClickhouseOrm
from app.dto.enum import LogLevel
from app.repositories.utils import get_offset_and_limit_clause
from app.schemas.gql.inputs.unit import UnitLogFilterInput
from app.schemas.pydantic.unit import UnitLogFilter


class UnitLogRepository:
    client: Client

    def __init__(
        self, client: Client = Depends(get_clickhouse_client)
    ) -> None:
        self.client = client
        self.orm = ClickhouseOrm(client)

    def create(self, unit_log: UnitLog) -> int:
        return self.orm.insert("unit_logs", [unit_log])

    def bulk_create(self, unit_logs: list[UnitLog]) -> int:
        return self.orm.insert("unit_logs", unit_logs)

    def get(self, uuid: uuid_pkg.UUID) -> UnitLog | None:
        return self.orm.get(
            f"select {UnitLog.get_keys()} from unit_logs where uuid = %(uuid)s",
            {"uuid": uuid},
            UnitLog,
        )

    def delete(self, uuid: uuid_pkg.UUID) -> None:
        query = "delete from unit_logs where unit_uuid = %(uuid)s"
        self.client.execute(query, {"uuid": uuid})

    def list(
        self, filters: UnitLogFilter | UnitLogFilterInput
    ) -> tuple[int, list[UnitLog]]:
        query = f"select {UnitLog.get_keys()} from unit_logs where unit_uuid = %(uuid)s"
        count_query = (
            "select count() as count from unit_logs where unit_uuid = %(uuid)s"
        )

        filters.level = [] if filters.level is None else filters.level

        if filters.level:
            filters.level = (
                filters.level.default
                if isinstance(filters.level, Query)
                else filters.level
            )
            data = ", ".join(
                [
                    f"'{item.value if isinstance(item, enum.Enum) else item}'"
                    for item in filters.level
                ]
            )
            level_append = f" AND level in ({data})"

            query += level_append
            count_query += level_append
        elif isinstance(filters.level, list) and not len(filters.level):
            level_append = " AND level in (0)"

            query += level_append
            count_query += level_append

        count = self.client.execute(count_query, {"uuid": filters.uuid})

        if filters.order_by_create_date:
            query += f" order by create_datetime {filters.order_by_create_date.value}"

        query += get_offset_and_limit_clause(filters)

        unit_logs = self.orm.get_many(
            query,
            {
                "uuid": filters.uuid,
                "limit": filters.limit,
                "offset": filters.offset,
            },
            UnitLog,
        )

        return count[0][0], unit_logs

    def aggregate(
        self,
        levels: list[str],
        since: datetime,
        until: datetime,
        unit_uuid: uuid_pkg.UUID | None = None,
        limit: int = 50,
    ) -> list[UnitLogAggregate]:
        since = _naive_utc(since)
        until = _naive_utc(until)
        params = {
            "levels": tuple(levels),
            "since": since,
            "until": until,
            "limit": limit,
        }
        if unit_uuid:
            params["unit_uuid"] = unit_uuid
            query = """
                SELECT level, text, count() AS count
                FROM unit_logs
                WHERE unit_uuid = %(unit_uuid)s
                  AND level IN %(levels)s
                  AND create_datetime >= %(since)s
                  AND create_datetime < %(until)s
                GROUP BY level, text
                ORDER BY count DESC
                LIMIT %(limit)s
            """
            rows = self.client.execute(query, params)
            return [
                UnitLogAggregate(
                    unit_uuid=unit_uuid,
                    level=self._level(row[0]),
                    text=str(row[1]),
                    count=int(row[2]),
                )
                for row in rows
            ]

        query = """
            SELECT unit_uuid, level, text, count() AS count
            FROM unit_logs
            WHERE level IN %(levels)s
              AND create_datetime >= %(since)s
              AND create_datetime < %(until)s
            GROUP BY unit_uuid, level, text
            ORDER BY count DESC
            LIMIT %(limit)s
        """
        rows = self.client.execute(query, params)
        return [
            UnitLogAggregate(
                unit_uuid=self._uuid(row[0]),
                level=self._level(row[1]),
                text=str(row[2]),
                count=int(row[3]),
            )
            for row in rows
        ]

    def count_errors_by_unit(
        self,
        unit_uuids: list[uuid_pkg.UUID],
        levels: list[str],
        since: datetime,
        until: datetime,
        limit: int = 10,
    ) -> list[UnitErrorCount]:
        if not unit_uuids:
            return []
        rows = self.client.execute(
            """
                SELECT unit_uuid, count() AS count
                FROM unit_logs
                WHERE unit_uuid IN %(unit_uuids)s
                  AND level IN %(levels)s
                  AND create_datetime >= %(since)s
                  AND create_datetime < %(until)s
                GROUP BY unit_uuid
                ORDER BY count DESC
                LIMIT %(limit)s
            """,
            {
                "unit_uuids": tuple(unit_uuids),
                "levels": tuple(levels),
                "since": _naive_utc(since),
                "until": _naive_utc(until),
                "limit": limit,
            },
        )
        return [
            UnitErrorCount(unit_uuid=self._uuid(row[0]), count=int(row[1]))
            for row in rows
        ]

    @staticmethod
    def _uuid(raw: object) -> uuid_pkg.UUID:
        if isinstance(raw, uuid_pkg.UUID):
            return raw
        return uuid_pkg.UUID(str(raw))

    @staticmethod
    def _level(raw: object) -> LogLevel:
        if isinstance(raw, LogLevel):
            return raw
        return LogLevel(str(raw))


def _naive_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)
