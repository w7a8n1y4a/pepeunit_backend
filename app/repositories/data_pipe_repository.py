from typing import Union

from clickhouse_driver import Client
from fastapi import Depends
from fastapi.params import Query

from app.configs.clickhouse import get_clickhouse_client
from app.configs.errors import DataPipeError
from app.dto.clickhouse.aggregation import Aggregation
from app.dto.clickhouse.n_records import NRecords
from app.dto.clickhouse.orm import ClickhouseOrm
from app.dto.clickhouse.time_window import TimeWindow
from app.dto.enum import ProcessingPolicyType
from app.schemas.pydantic.unit_node import DataPipeFilter


class DataPipeRepository:
    client: Client

    def __init__(self, client: Client = Depends(get_clickhouse_client)) -> None:
        self.client = client
        self.orm = ClickhouseOrm(client)

    @staticmethod
    def _get_type(policy: ProcessingPolicyType):
        match policy:
            case ProcessingPolicyType.N_RECORDS:
                return NRecords
            case ProcessingPolicyType.TIME_WINDOW:
                return TimeWindow
            case ProcessingPolicyType.AGGREGATION:
                return Aggregation

    def list(self, filters: Union[DataPipeFilter]) -> tuple[int, list[Union[NRecords, TimeWindow, Aggregation]]]:
        query = ''
        match filters.type:
            case ProcessingPolicyType.LAST_VALUE:
                raise DataPipeError('LastValue type is not supported on this function')
            case ProcessingPolicyType.N_RECORDS:
                query = """
                    SELECT
                        *
                    FROM
                    (
                        SELECT
                            *,
                            row_number() OVER (PARTITION BY unit_node_uuid ORDER BY create_datetime DESC) AS id
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

        if filters.type != ProcessingPolicyType.AGGREGATION and filters.search_string:
            query += f" AND state ilike %(search_string)s"

        if filters.type == ProcessingPolicyType.AGGREGATION:

            filters.aggregation_type = [] if filters.aggregation_type is None else filters.aggregation_type

            if filters.aggregation_type:
                filters.aggregation_type = (
                    filters.aggregation_type.default
                    if isinstance(filters.aggregation_type, Query)
                    else filters.aggregation_type
                )
                data = ', '.join([f"'{item}'" for item in filters.aggregation_type])
                level_append = f' AND aggregation_type in ({data})'

                query += level_append
            elif isinstance(filters.aggregation_type, list) and not len(filters.aggregation_type):
                level_append = f' AND aggregation_type in (0)'

                query += level_append

            if filters.time_window_size is not None:
                query += f" AND time_window_size = {filters.time_window_size}"

            if filters.start_agg_window_datetime:
                query += f" AND start_window_datetime >= {filters.start_agg_window_datetime}"

            if filters.end_agg_window_datetime:
                query += f" AND start_window_datetime <= {filters.end_agg_window_datetime}"

        if filters.start_create_datetime:
            query += f" AND create_datetime >= {filters.start_create_datetime}"

        if filters.end_create_datetime:
            query += f" AND create_datetime <= {filters.end_create_datetime}"

        count = len(self.client.execute(query, {'uuid': filters.uuid, 'search_string': f'%{filters.search_string}%'}))

        if filters.order_by_create_date:
            # otherwise the order breaks down
            if filters.type == ProcessingPolicyType.N_RECORDS:
                query += f" order by id {filters.order_by_create_date.value}"
            else:
                query += f" order by create_datetime {filters.order_by_create_date.value}"

        if filters.limit:
            query += f" limit %(limit)s"

        if filters.offset:
            query += f" offset %(offset)s"

        unit_logs = self.orm.get_many(
            query,
            {
                'uuid': filters.uuid,
                'search_string': f'%{filters.search_string}%',
                'limit': filters.limit,
                'offset': filters.offset,
            },
            self._get_type(filters.type),
        )

        return count, unit_logs
