import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class ActivePeriodType(str, Enum):
    PERMANENT = "Permanent"
    FROM_DATE = "FromDate"
    TO_DATE = "ToDate"
    DATE_RANGE = "DateRange"


class ActivePeriod(BaseModel):
    type: ActivePeriodType
    start: Optional[datetime.datetime] = None
    end: Optional[datetime.datetime] = None


class TypeInputValue(str, Enum):
    TEXT = "Text"
    NUMBER = "Number"


class FilterTypeValueFiltering(str, Enum):
    WHITELIST = "WhiteList"
    BLACKLIST = "BlackList"


class FilterTypeValueThreshold(str, Enum):
    MIN = "Min"
    MAX = "Max"
    RANGE = "Range"


class FiltersConfig(BaseModel):
    type_input_value: TypeInputValue

    type_value_filtering: Optional[FilterTypeValueFiltering] = None
    filtering_values: Optional[list[str | int]] = None

    type_value_threshold: Optional[FilterTypeValueThreshold] = None
    threshold_min: Optional[int] = None
    threshold_max: Optional[int] = None

    max_rate: str = "0s"
    last_unique_check: bool = False
    max_size: int = 0


class TransformationConfig(BaseModel):
    multiplication: Optional[bool] = None
    multiplication_ratio: Optional[float] = None

    round: Optional[bool] = None
    round_decimal_point: Optional[int] = None

    slice: Optional[bool] = None
    slice_start: Optional[int] = None
    slice_end: Optional[int] = None


class ProcessingPolicyType(str, Enum):
    LAST_VALUE = "LastValue"
    N_RECORDS = "NRecords"
    TIME_WINDOW = "TimeWindow"
    AGGREGATION = "Aggregation"


class AggregationFunctions(str, Enum):
    AVG = "Avg"
    MIN = "Min"
    MAX = "Max"
    SUM = "Sum"


class ProcessingPolicyConfig(BaseModel):
    policy_type: ProcessingPolicyType
    n_records_count: Optional[int] = None
    time_window_size: Optional[str] = None
    aggregation_functions: Optional[AggregationFunctions] = None


class DataPipeConfig(BaseModel):
    active_period: ActivePeriod
    filters: FiltersConfig
    transformations: Optional[TransformationConfig] = None
    processing_policy: ProcessingPolicyConfig


def is_valid_data_pipe_config(data_pipe: dict) -> DataPipeConfig:
    data_pipe_struct = DataPipeConfig(**data_pipe)

    return data_pipe_struct
