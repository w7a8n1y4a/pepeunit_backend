import builtins
import csv
import os
import uuid
import zipfile
from datetime import UTC, datetime
from io import StringIO

from clickhouse_driver import Client
from fastapi import Depends
from fastapi.params import Query
from pydantic import BaseModel
from sqlmodel import Session

from app.configs.clickhouse import get_clickhouse_client
from app.configs.db import get_session
from app.configs.errors import DataPipeError
from app.domain.unit_node_model import UnitNode
from app.dto.clickhouse.aggregation import Aggregation
from app.dto.clickhouse.last_value import LastValue
from app.dto.clickhouse.n_records import NRecords
from app.dto.clickhouse.orm import ClickhouseOrm
from app.dto.clickhouse.time_window import TimeWindow
from app.dto.enum import ProcessingPolicyType
from app.schemas.pydantic.unit_node import DataPipeFilter


class DataPipeRepository:
    client: Client

    def __init__(
        self,
        client: Client = Depends(get_clickhouse_client),
        db: Session = Depends(get_session),
    ) -> None:
        self.client = client
        self.db = db
        self.orm = ClickhouseOrm(client)

    def bulk_create(self, policy: ProcessingPolicyType, data: list[BaseModel]):
        if policy == ProcessingPolicyType.LAST_VALUE:
            msg = "Bulk create for LastValue not available"
            raise DataPipeError(msg)

        table_names = {
            ProcessingPolicyType.AGGREGATION: "aggregation_entry",
            ProcessingPolicyType.N_RECORDS: "n_last_entry",
            ProcessingPolicyType.TIME_WINDOW: "window_entry",
        }

        self.orm.insert(table_names[policy], data)

    @staticmethod
    def _get_type(policy: ProcessingPolicyType):
        match policy:
            case ProcessingPolicyType.LAST_VALUE:
                return LastValue
            case ProcessingPolicyType.N_RECORDS:
                return NRecords
            case ProcessingPolicyType.TIME_WINDOW:
                return TimeWindow
            case ProcessingPolicyType.AGGREGATION:
                return Aggregation

    def list_postgres(
        self, filters: DataPipeFilter
    ) -> tuple[int, list[LastValue]]:
        unit_node = (
            self.db.query(UnitNode)
            .filter(UnitNode.uuid == filters.uuid)
            .first()
        )

        if not unit_node:
            return 0, []
        return 1, [
            LastValue(
                unit_node_uuid=unit_node.uuid,
                state=unit_node.state,
                last_update_datetime=unit_node.last_update_datetime,
            )
        ]

    def list(
        self, filters: DataPipeFilter
    ) -> tuple[int, list[NRecords | TimeWindow | Aggregation | LastValue]]:
        query = ""
        match filters.type:
            case ProcessingPolicyType.LAST_VALUE:
                return self.list_postgres(filters=filters)
            case ProcessingPolicyType.N_RECORDS:
                query = """
                    SELECT
                        *
                    FROM
                    (
                        SELECT
                            *,
                            row_number() OVER (PARTITION BY unit_node_uuid ORDER BY create_datetime ASC) AS id
                        FROM
                            n_last_entry
                        WHERE
                            unit_node_uuid = %(uuid)s
                    ) AS numbered_entries
                    WHERE
                        unit_node_uuid = %(uuid)s
                """

            case ProcessingPolicyType.TIME_WINDOW:
                query = f"select {TimeWindow.get_keys()} from window_entry where unit_node_uuid = %(uuid)s"
            case ProcessingPolicyType.AGGREGATION:
                query = f"select {Aggregation.get_keys()} from aggregation_entry where unit_node_uuid = %(uuid)s"

        if filters.type == ProcessingPolicyType.AGGREGATION:
            filters.aggregation_type = (
                []
                if filters.aggregation_type is None
                else filters.aggregation_type
            )

            query = self._apply_aggregation_filters(query, filters)

        query = self._apply_common_filters(query, filters)

        count = len(
            self.client.execute(
                query,
                {
                    "uuid": filters.uuid,
                    "search_string": f"%{filters.search_string}%",
                },
            )
        )

        if filters.order_by_create_date:
            # otherwise the order breaks down
            if filters.type == ProcessingPolicyType.N_RECORDS:
                query += f" order by id {filters.order_by_create_date.value}"
            else:
                query += f" order by create_datetime {filters.order_by_create_date.value}"

        if filters.limit:
            query += " limit %(limit)s"

        if filters.offset:
            query += " offset %(offset)s"

        unit_logs = self.orm.get_many(
            query,
            {
                "uuid": filters.uuid,
                "search_string": f"%{filters.search_string}%",
                "limit": filters.limit,
                "offset": filters.offset,
            },
            self._get_type(filters.type),
        )

        return count, unit_logs

    def _apply_aggregation_filters(
        self, query: str, filters: DataPipeFilter
    ) -> str:
        if filters.aggregation_type:
            filters.aggregation_type = (
                filters.aggregation_type.default
                if isinstance(filters.aggregation_type, Query)
                else filters.aggregation_type
            )
            data = ", ".join(
                [f"'{item}'" for item in filters.aggregation_type]
            )
            level_append = f" AND aggregation_type in ({data})"

            query += level_append
        elif isinstance(filters.aggregation_type, list) and not len(
            filters.aggregation_type
        ):
            level_append = " AND aggregation_type in (0)"

            query += level_append

        if filters.time_window_size is not None:
            query += f" AND time_window_size = {filters.time_window_size}"

        if filters.start_agg_window_datetime:
            query += f" AND end_window_datetime >= '{filters.start_agg_window_datetime}'"

        if filters.end_agg_window_datetime:
            query += f" AND end_window_datetime <= '{filters.end_agg_window_datetime}'"

        return query

    def _apply_common_filters(
        self, query: str, filters: DataPipeFilter
    ) -> str:
        if (
            filters.search_string
            and filters.type != ProcessingPolicyType.AGGREGATION
        ):
            query += " AND state ILIKE %(search_string)s"

        if filters.start_create_datetime:
            query += (
                f" AND create_datetime >= '{filters.start_create_datetime}'"
            )

        if filters.end_create_datetime:
            query += f" AND create_datetime <= '{filters.end_create_datetime}'"

        if filters.relative_interval:
            current_datetime = datetime.now(UTC)
            query += f" AND create_datetime >= '{(current_datetime - filters.relative_interval).replace(tzinfo=None)}'"

        return query

    def _apply_aggregation_filters(
        self, query: str, filters: DataPipeFilter
    ) -> str:
        """
        Расширяет базовый запрос условиями, относящимися к AGGREGATION.
        """
        # 🟢 обработка aggregation_type
        aggregation_type = filters.aggregation_type or []
        if isinstance(aggregation_type, Query):
            aggregation_type = aggregation_type.default

        if aggregation_type:  # если список не пустой
            data = ", ".join([f"'{item}'" for item in aggregation_type])
            query += f" AND aggregation_type IN ({data})"
        elif isinstance(aggregation_type, list):  # если пустой список
            query += " AND aggregation_type IN (0)"  # гарантируем, что вернётся пустой результат

        # 🟢 фильтрация по размеру окна
        if filters.time_window_size is not None:
            query += f" AND time_window_size = {filters.time_window_size}"

        # 🟢 фильтрация по времени начала/конца окна агрегации
        if filters.start_agg_window_datetime:
            query += f" AND end_window_datetime >= '{filters.start_agg_window_datetime}'"

        if filters.end_agg_window_datetime:
            query += f" AND end_window_datetime <= '{filters.end_agg_window_datetime}'"

        return query

    def bulk_delete(self, uuids: builtins.list[str]) -> None:
        tables = ["n_last_entry", "window_entry", "aggregation_entry"]
        uuid_list = ", ".join([f"'{uuid}'" for uuid in uuids])
        for table_name in tables:
            query = f"ALTER TABLE {table_name} DELETE WHERE unit_node_uuid IN ({uuid_list})"
            self.client.execute(query)

    @staticmethod
    def models_to_csv(
        data: builtins.list[NRecords | TimeWindow | Aggregation],
    ) -> str:
        if not len(data):
            msg = "No data found"
            raise DataPipeError(msg)

        csv_data = StringIO()
        writer = csv.writer(csv_data)
        writer.writerow(data[0].dict().keys())
        for item in data:
            writer.writerow(item.dict().values())

        result = csv_data.getvalue()

        target_uuid = uuid.uuid4()
        file_name = f"dp_data_{target_uuid}.csv"
        file_path = f"tmp/{file_name}"
        zip_path = f"tmp/dp_data_{target_uuid}.zip"

        with open(file_path, "w") as f:
            f.write(result)

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(file_path, arcname=file_name)

        os.remove(file_path)

        return zip_path
