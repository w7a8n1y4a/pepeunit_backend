import datetime
from numbers import Real
from typing import Optional, Union

from pydantic import BaseModel, Field, ValidationError, model_validator

from app import settings
from app.configs.errors import DataPipeError
from app.dto.enum import (
    ActivePeriodType,
    AggregationFunctions,
    DataPipeStage,
    FilterTypeValueFiltering,
    FilterTypeValueThreshold,
    ProcessingPolicyType,
    TypeInputValue,
)
from app.schemas.pydantic.unit_node import DataPipeValidationErrorRead
from app.utils.utils import snake_to_camel


class ActivePeriod(BaseModel):
    type: ActivePeriodType
    start: Optional[datetime.datetime] = None
    end: Optional[datetime.datetime] = None

    @model_validator(mode="after")
    def check_active_period(cls, self):
        if self.type == ActivePeriodType.FROM_DATE and not self.start:
            raise ValueError("start must be provided for FROM_DATE")
        if self.type == ActivePeriodType.TO_DATE and not self.end:
            raise ValueError("end must be provided for TO_DATE")
        if self.type == ActivePeriodType.DATE_RANGE:
            if not self.start or not self.end:
                raise ValueError("start and end must be provided for DATE_RANGE")
            if self.start >= self.end:
                raise ValueError("start must be before end for DATE_RANGE")
        return self


class FiltersConfig(BaseModel):
    type_input_value: TypeInputValue

    type_value_filtering: Optional[FilterTypeValueFiltering] = None
    filtering_values: Optional[list[Union[str, int, float]]] = None

    type_value_threshold: Optional[FilterTypeValueThreshold] = None
    threshold_min: Optional[int] = None
    threshold_max: Optional[int] = None

    max_rate: int = Field(ge=0, le=86400)
    last_unique_check: bool = False
    max_size: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_filters(self):
        if self.type_value_filtering and self.filtering_values:
            if self.type_input_value == TypeInputValue.NUMBER and not all(
                isinstance(x, Real) for x in self.filtering_values
            ):
                raise ValueError("filtering_values must be numeric for NUMBER input")
            if self.type_input_value == TypeInputValue.TEXT and not all(
                isinstance(x, str) for x in self.filtering_values
            ):
                raise ValueError("filtering_values must be strings for TEXT input")

        if self.type_input_value == TypeInputValue.NUMBER:
            if (
                self.type_value_threshold == FilterTypeValueThreshold.MIN
                and self.threshold_min is None
            ):
                raise ValueError("threshold_min is required for MIN threshold")
            if (
                self.type_value_threshold == FilterTypeValueThreshold.MAX
                and self.threshold_max is None
            ):
                raise ValueError("threshold_max is required for MAX threshold")
            if self.type_value_threshold == FilterTypeValueThreshold.RANGE:
                if self.threshold_min is None or self.threshold_max is None:
                    raise ValueError(
                        "Both threshold_min and threshold_max are required for RANGE threshold"
                    )
                if self.threshold_min >= self.threshold_max:
                    raise ValueError("threshold_min must be less than threshold_max")

        if self.max_size > settings.mqtt_max_payload_size * 1024:
            raise ValueError(
                f"max_size must be <= {settings.mqtt_max_payload_size * 1024}"
            )

        return self


class TransformationConfig(BaseModel):
    multiplication_ratio: Optional[float] = None
    round_decimal_point: Optional[int] = Field(default=None, ge=0, le=7)
    slice_start: Optional[int] = None
    slice_end: Optional[int] = None


class ProcessingPolicyConfig(BaseModel):
    policy_type: ProcessingPolicyType
    n_records_count: Optional[int] = None
    time_window_size: Optional[int] = None
    aggregation_functions: Optional[AggregationFunctions] = None

    @model_validator(mode="after")
    def validate_processing(self):
        if self.policy_type == ProcessingPolicyType.N_RECORDS:
            if self.n_records_count is None:
                raise ValueError("n_records_count is required for N_RECORDS")
            if not (0 < self.n_records_count <= 1024):
                raise ValueError("n_records_count must be between 1 and 1024")

        if self.policy_type in [
            ProcessingPolicyType.TIME_WINDOW,
            ProcessingPolicyType.AGGREGATION,
        ]:
            if self.time_window_size is None:
                raise ValueError("time_window_size is required")
            if self.time_window_size not in settings.time_window_sizes:
                raise ValueError(
                    f"Invalid time_window_size. Must be one of: {settings.time_window_sizes}"
                )

        if (
            self.policy_type == ProcessingPolicyType.AGGREGATION
            and self.aggregation_functions is None
        ):
            raise ValueError("aggregation_functions is required for AGGREGATION")

        return self


class DataPipeConfig(BaseModel):
    active_period: ActivePeriod
    filters: FiltersConfig
    transformations: Optional[TransformationConfig] = None
    processing_policy: ProcessingPolicyConfig


def format_validation_error_dict(
    e: ValidationError,
) -> list[DataPipeValidationErrorRead]:
    validation_errors = []
    for err in e.errors():
        validation_errors.append(
            DataPipeValidationErrorRead(
                stage=DataPipeStage(snake_to_camel(err["loc"][0])),
                message=err["msg"],
            )
        )

    return validation_errors


def is_valid_data_pipe_config(
    data: dict, is_business_validator: bool = False
) -> DataPipeConfig | list[DataPipeValidationErrorRead]:
    if data is None:
        raise DataPipeError("DataPipe is None")

    if is_business_validator:
        try:
            return DataPipeConfig.model_validate(data)
        except ValidationError as e:
            raise DataPipeError(
                "{} validation errors for DataPipeConfig".format(len(e.errors()))
            )
    else:
        try:
            DataPipeConfig.model_validate(data)
            return []
        except ValidationError as e:
            return format_validation_error_dict(e)
