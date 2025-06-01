import datetime
from enum import Enum
from numbers import Real
from typing import Optional

from pydantic import BaseModel

from app import settings
from app.configs.errors import DataPipeError


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
    filtering_values: Optional[list[str | int | float]] = None

    type_value_threshold: Optional[FilterTypeValueThreshold] = None
    threshold_min: Optional[int] = None
    threshold_max: Optional[int] = None

    max_rate: int = 0
    last_unique_check: bool = False
    max_size: int = 0


class TransformationConfig(BaseModel):
    multiplication_ratio: Optional[float] = None

    round_decimal_point: Optional[int] = None

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


def all_elements_are_strings(lst: list):
    return all(isinstance(element, str) for element in lst)


def all_elements_are_numbers(lst: list):
    return all(isinstance(x, Real) for x in lst)


def is_valid_data_pipe_config(data_pipe_dict: dict) -> DataPipeConfig:
    data_pipe = DataPipeConfig(**data_pipe_dict)

    validation_rules = {
        ActivePeriodType.FROM_DATE: ["start"],
        ActivePeriodType.TO_DATE: ["end"],
        ActivePeriodType.DATE_RANGE: ["start", "end"],
    }

    # check correct active_period
    for param in validation_rules.get(data_pipe.active_period.type, []):
        if not getattr(data_pipe.active_period, param):
            raise DataPipeError(
                'For ActivePeriod stage with type "{}", parameter "{}" should not be None'.format(
                    data_pipe.active_period.type, param
                )
            )

    if data_pipe.active_period.type == ActivePeriodType.DATE_RANGE:
        if data_pipe.active_period.start >= data_pipe.active_period.end:
            raise DataPipeError(
                'For ActivePeriod stage with type "{}", start time must be strictly less than end time'.format(
                    data_pipe.active_period.type
                )
            )

    # check correct filters values black/white list
    if data_pipe.filters.type_value_filtering and data_pipe.filters.filtering_values:
        if data_pipe.filters.type_input_value == TypeInputValue.NUMBER and not all_elements_are_numbers(
            data_pipe.filters.filtering_values
        ):
            raise DataPipeError(
                'For Filters stage with type "{}", filtering_values must be of numeric type'.format(
                    data_pipe.filters.type_input_value,
                )
            )
        elif data_pipe.filters.type_input_value == TypeInputValue.TEXT and not all_elements_are_strings(
            data_pipe.filters.filtering_values
        ):
            raise DataPipeError(
                'For Filters stage with type "{}", filtering_values must be of string type'.format(
                    data_pipe.filters.type_input_value,
                )
            )

    validation_rules = {
        FilterTypeValueThreshold.MAX: ["threshold_max"],
        FilterTypeValueThreshold.MIN: ["threshold_min"],
        FilterTypeValueThreshold.RANGE: ["threshold_min", "threshold_max"],
    }

    # check correct filters threshold
    if data_pipe.filters.type_input_value == TypeInputValue.NUMBER:
        for param in validation_rules.get(data_pipe.filters.type_value_threshold, []):
            if not getattr(data_pipe.filters, param):
                raise DataPipeError(
                    'For Filters stage with type "{}", parameter "{}" should not be None'.format(
                        data_pipe.filters.type_value_threshold, param
                    )
                )
        if data_pipe.filters.type_value_threshold == FilterTypeValueThreshold.RANGE:
            if data_pipe.filters.threshold_min >= data_pipe.filters.threshold_max:
                raise DataPipeError(
                    'For Filters stage with type "{}", threshold_min must be strictly less than threshold_max'.format(
                        data_pipe.filters.type_value_threshold
                    )
                )

    # check filters max_rate
    if data_pipe.filters.max_rate < 0 or data_pipe.filters.max_rate > 86400:
        raise DataPipeError('For Filters max_rate must satisfy inequalities: max_rate >= 0 and max_rate <= 86400')

    # check filters max_size
    if data_pipe.filters.max_size < 0 or data_pipe.filters.max_size > settings.mqtt_max_payload_size * 1024:
        raise DataPipeError(
            'For Filters max_size must satisfy inequalities: max_size >= 0 and max_rate <= {}'.format(
                settings.mqtt_max_payload_size * 1024
            )
        )

    # check transformations decimal point
    if data_pipe.transformations.round_decimal_point:
        if data_pipe.transformations.round_decimal_point <= 0 and data_pipe.transformations.round_decimal_point > 7:
            raise DataPipeError(
                'For Filters round_decimal_point must satisfy inequalities: round_decimal_point >= 0 and round_decimal_point <= 7'
            )

    # check n_records policy correction
    if data_pipe.processing_policy.policy_type == ProcessingPolicyType.N_RECORDS:
        if data_pipe.processing_policy.n_records_count is None:
            raise DataPipeError(
                'For ProcessingPolicy stage with type "{}", parameter n_records_count should not be None'.format(
                    data_pipe.processing_policy.policy_type
                )
            )
        if data_pipe.processing_policy.n_records_count <= 0 and data_pipe.processing_policy.n_records_count > 1024:
            raise DataPipeError(
                'For ProcessingPolicy stage with type "{}", n_records_count must satisfy inequalities: n_records_count >= 0 and n_records_count <= 1024'.format(
                    data_pipe.processing_policy.policy_type
                )
            )

    # check time_window policy correction
    elif data_pipe.processing_policy.policy_type == ProcessingPolicyType.TIME_WINDOW:
        if data_pipe.processing_policy.time_window_size is None:
            raise DataPipeError(
                'For ProcessingPolicy stage with type "{}", parameter time_window_size should not be None'.format(
                    data_pipe.processing_policy.policy_type
                )
            )
        if data_pipe.processing_policy.time_window_size not in settings.time_window_sizes:
            raise DataPipeError(
                'For ProcessingPolicy stage with type "{}", time_window_size in seconds must belong to the set: {}'.format(
                    data_pipe.processing_policy.policy_type, settings.time_window_sizes
                )
            )

    # check aggregation policy correction
    elif data_pipe.processing_policy.policy_type == ProcessingPolicyType.AGGREGATION:
        if data_pipe.processing_policy.time_window_size is None:
            raise DataPipeError(
                'For ProcessingPolicy stage with type "{}", parameter time_window_size should not be None'.format(
                    data_pipe.processing_policy.policy_type
                )
            )

        if data_pipe.processing_policy.aggregation_functions is None:
            raise DataPipeError(
                'For ProcessingPolicy stage with type "{}", parameter aggregation_functions should not be None'.format(
                    data_pipe.processing_policy.policy_type
                )
            )

        if data_pipe.processing_policy.time_window_size not in settings.time_window_sizes:
            raise DataPipeError(
                'For ProcessingPolicy stage with type "{}", time_window_size in seconds must belong to the set: {}'.format(
                    data_pipe.processing_policy.policy_type, settings.time_window_sizes
                )
            )

    return data_pipe
