import csv
import enum
import uuid as uuid_pkg
from datetime import datetime, timedelta
from io import StringIO
from typing import AsyncGenerator, Union

from fastapi import UploadFile
from strawberry.file_uploads import Upload

from app import settings
from app.configs.errors import DataPipeError
from app.dto.clickhouse.aggregation import Aggregation
from app.dto.clickhouse.n_records import NRecords
from app.dto.clickhouse.time_window import TimeWindow
from app.dto.enum import (
    ActivePeriodType,
    FilterTypeValueFiltering,
    FilterTypeValueThreshold,
    ProcessingPolicyType,
    TypeInputValue,
)
from app.validators.data_pipe import DataPipeConfig


class AvailableCSVKeys(enum.Enum):
    STATE = "state"
    CREATE_DATETIME = "create_datetime"
    START_WINDOW_DATETIME = "start_window_datetime"
    END_WINDOW_DATETIME = "end_window_datetime"


class StreamingCSVValidator:
    def __init__(self, config: DataPipeConfig):
        self.config = config
        self.current_row = 0

    async def iter_validated_streaming(
        self, unit_node_uuid: uuid_pkg.UUID, upload_file: Union[Upload, UploadFile]
    ) -> AsyncGenerator[Union[TimeWindow, NRecords, Aggregation], None]:
        content = await upload_file.read()
        csv_content = content.decode('utf-8')

        reader = csv.DictReader(StringIO(csv_content))
        previous_create_datetime = None
        previous_state = None
        previous_end_window_datetime = None

        for row in reader:
            self.current_row += 1

            create_datetime = self._parse_datetime(row[AvailableCSVKeys.CREATE_DATETIME.value])
            self.check_monotonicity(create_datetime, previous_create_datetime)

            state = self._is_valid_state(row[AvailableCSVKeys.STATE.value])

            end_window_datetime = None
            if self.config.processing_policy.policy_type == ProcessingPolicyType.AGGREGATION:
                end_window_datetime = self._parse_datetime(row[AvailableCSVKeys.END_WINDOW_DATETIME.value])

            self.check_active_period(create_datetime)
            self.check_black_white_list(state)
            self.check_threshold(state)
            self.check_max_rate(create_datetime, previous_create_datetime)
            self.check_last_unique(state, previous_state)
            self.check_max_size(state)

            match self.config.processing_policy.policy_type:
                case ProcessingPolicyType.TIME_WINDOW:
                    self.check_window_entry(create_datetime)

                    expiration_datetime = create_datetime + timedelta(
                        seconds=self.config.processing_policy.time_window_size
                    )
                    yield TimeWindow(
                        uuid=uuid_pkg.uuid4(),
                        unit_node_uuid=unit_node_uuid,
                        state=str(state),
                        state_type=self.config.filters.type_input_value,
                        create_datetime=create_datetime,
                        expiration_datetime=expiration_datetime,
                        size=len(str(state)),
                    )

                case ProcessingPolicyType.N_RECORDS:
                    self.check_n_last_entry()

                    yield NRecords(
                        id=self.current_row,
                        uuid=uuid_pkg.uuid4(),
                        unit_node_uuid=unit_node_uuid,
                        state=str(state),
                        state_type=self.config.filters.type_input_value,
                        create_datetime=create_datetime,
                        max_count=self.config.processing_policy.n_records_count,
                        size=len(str(state)),
                    )

                case ProcessingPolicyType.AGGREGATION:
                    self.check_aggregation_entry(
                        row, create_datetime, end_window_datetime, previous_end_window_datetime
                    )

                    start_window_datetime = self._parse_datetime(row[AvailableCSVKeys.START_WINDOW_DATETIME.value])
                    yield Aggregation(
                        uuid=uuid_pkg.uuid4(),
                        unit_node_uuid=unit_node_uuid,
                        state=float(state),
                        aggregation_type=self.config.processing_policy.aggregation_functions,
                        time_window_size=self.config.processing_policy.time_window_size,
                        create_datetime=create_datetime,
                        start_window_datetime=start_window_datetime,
                        end_window_datetime=end_window_datetime,
                    )

            previous_create_datetime = create_datetime
            previous_state = state
            if self.config.processing_policy.policy_type == ProcessingPolicyType.AGGREGATION:
                previous_end_window_datetime = end_window_datetime

    def check_window_entry(self, create_datetime: datetime) -> None:
        datetime_now = datetime.utcnow()
        if create_datetime > datetime_now or create_datetime < datetime_now - timedelta(
            seconds=self.config.processing_policy.time_window_size
        ):
            raise DataPipeError(
                f"Row {self.current_row}: For {self.config.processing_policy.policy_type.value}: create_datetime is outside the range of valid values from time_window_size"
            )

    def check_n_last_entry(self) -> None:
        if self.current_row > self.config.processing_policy.n_records_count:
            raise DataPipeError(
                f"For {self.config.processing_policy.policy_type.value}: number of records exceeds limit n_records_count"
            )

    def check_aggregation_entry(
        self,
        row: dict,
        create_datetime: datetime,
        end_window_datetime: datetime,
        previous_end_window_datetime: datetime | None,
    ) -> None:

        start_window_datetime = self._parse_datetime(row[AvailableCSVKeys.START_WINDOW_DATETIME.value])

        if start_window_datetime.second != 0 or end_window_datetime.second != 0:
            raise DataPipeError(
                f"Row {self.current_row}: For {self.config.processing_policy.policy_type.value}: start_window_datetime or end_window_datetime have seconds"
            )

        if end_window_datetime < start_window_datetime:
            raise DataPipeError(
                f"Row {self.current_row}: For {self.config.processing_policy.policy_type.value}: end_window_datetime < start_window_datetime"
            )

        actual_delta = (create_datetime - end_window_datetime).total_seconds()
        if abs(actual_delta) >= settings.time_window_sizes[0]:
            raise DataPipeError(
                f"Row {self.current_row}: For {self.config.processing_policy.policy_type.value}: The difference between create_datetime and end_window_datetime is greater than the minimum time_window_sizes"
            )

        actual_delta = (end_window_datetime - start_window_datetime).total_seconds()
        if actual_delta != self.config.processing_policy.time_window_size:
            raise DataPipeError(
                f"Row {self.current_row}: For {self.config.processing_policy.policy_type.value}: config time_window_size is not {actual_delta} end_window_datetime - start_window_datetime"
            )
        if previous_end_window_datetime:
            actual_delta = (end_window_datetime - previous_end_window_datetime).total_seconds()
            if actual_delta % self.config.processing_policy.time_window_size != 0:
                raise DataPipeError(
                    f"Row {self.current_row}: For {self.config.processing_policy.policy_type.value}: config time_window_size is not {actual_delta} end_window_datetime - previous_end_window_datetime"
                )

    def check_active_period(self, create_datetime: datetime) -> None:

        match self.config.active_period.type:
            case ActivePeriodType.PERMANENT:
                return
            case ActivePeriodType.FROM_DATE:
                if self.config.active_period.start > create_datetime:
                    raise DataPipeError(
                        f"Row {self.current_row}: create_datetime is outside the start of the active period"
                    )
            case ActivePeriodType.TO_DATE:
                if self.config.active_period.end < create_datetime:
                    raise DataPipeError(
                        f"Row {self.current_row}: create_datetime is outside the end of the active period"
                    )
            case ActivePeriodType.DATE_RANGE:
                if self.config.active_period.start > create_datetime or self.config.active_period.end < create_datetime:
                    raise DataPipeError(
                        f"Row {self.current_row}: create_datetime is outside the start or end of the active period"
                    )

    def check_black_white_list(self, state: str | float) -> None:
        if self.config.filters.type_value_filtering:
            match self.config.filters.type_value_filtering:
                case FilterTypeValueFiltering.WHITELIST:
                    if not self._state_in_list(state):
                        raise DataPipeError(f"Row {self.current_row}: state not in whitelist")
                case FilterTypeValueFiltering.BLACKLIST:
                    if self._state_in_list(state):
                        raise DataPipeError(f"Row {self.current_row}: state in blacklist")

    def check_threshold(self, state: float) -> None:
        if self.config.filters.type_value_threshold:
            if self.config.filters.type_input_value == TypeInputValue.NUMBER:
                match self.config.filters.type_value_threshold:
                    case FilterTypeValueThreshold.MIN:
                        if state < self.config.filters.threshold_min:
                            raise DataPipeError(f"Row {self.current_row}: state < threshold_min")
                    case FilterTypeValueThreshold.MAX:
                        if state > self.config.filters.threshold_max:
                            raise DataPipeError(f"Row {self.current_row}: state > threshold_max")
                    case FilterTypeValueThreshold.RANGE:
                        if state < self.config.filters.threshold_min or state > self.config.filters.threshold_max:
                            raise DataPipeError(
                                f"Row {self.current_row}: state < threshold_min or state > threshold_max"
                            )

    def check_max_rate(self, create_datetime: datetime, previous_create_datetime: datetime | None) -> None:
        if self.config.processing_policy.policy_type in [
            ProcessingPolicyType.N_RECORDS,
            ProcessingPolicyType.TIME_WINDOW,
        ]:
            if self.config.filters.max_rate > 0 and previous_create_datetime:
                if previous_create_datetime + timedelta(seconds=self.config.filters.max_rate) > create_datetime:
                    raise DataPipeError(
                        f"Row {self.current_row}: the time difference between the previous entry and the current one, less than max_rate"
                    )

    def check_last_unique(self, state: str | float, previous_state: str | float) -> None:
        if self.config.processing_policy.policy_type in [
            ProcessingPolicyType.N_RECORDS,
            ProcessingPolicyType.TIME_WINDOW,
        ]:
            if self.config.filters.last_unique_check and previous_state is not None:
                if state == previous_state:
                    raise DataPipeError(f"Row {self.current_row}: previous_state is identical current state")

    def check_max_size(self, state: str | float) -> None:
        if self.config.filters.max_size > 0:
            if len(str(state)) > self.config.filters.max_size:
                raise DataPipeError(f"Row {self.current_row}: length state > max_size")

    def check_monotonicity(self, create_datetime: datetime, previous_create_datetime: datetime | None):
        if previous_create_datetime:
            if create_datetime < previous_create_datetime:
                raise DataPipeError(f"Row {self.current_row}: create_datetime < previous_create_datetime")

    def _state_in_list(self, state: str | float) -> bool:
        for filter_value in self.config.filters.filtering_values:
            match self.config.filters.type_input_value:
                case TypeInputValue.TEXT:
                    if str(filter_value) == state:
                        return True
                case TypeInputValue.NUMBER:
                    if float(filter_value) == state:
                        return True
        return False

    def _is_valid_state(self, state) -> str | float:
        match self.config.filters.type_input_value:
            case TypeInputValue.TEXT:
                try:
                    return str(state)
                except ValueError:
                    raise DataPipeError(f"Row {self.current_row}: state is not a valid python string")
            case TypeInputValue.NUMBER:
                try:
                    return float(state)
                except ValueError:
                    raise DataPipeError(f"Row {self.current_row}: state is not a valid python float")

    @staticmethod
    def _parse_datetime(datetime_str: str) -> datetime:
        if '.' in datetime_str:
            return datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S.%f')
        else:
            return datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')
