import datetime
from numbers import Real

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
    start: datetime.datetime | None = None
    end: datetime.datetime | None = None

    @model_validator(mode="after")
    def check_active_period(cls, self):
        if self.type == ActivePeriodType.FROM_DATE and not self.start:
            msg = "start must be provided for FROM_DATE"
            raise ValueError(msg)
        if self.type == ActivePeriodType.TO_DATE and not self.end:
            msg = "end must be provided for TO_DATE"
            raise ValueError(msg)
        if self.type == ActivePeriodType.DATE_RANGE:
            if not self.start or not self.end:
                msg = "start and end must be provided for DATE_RANGE"
                raise ValueError(msg)
            if self.start >= self.end:
                msg = "start must be before end for DATE_RANGE"
                raise ValueError(msg)
        return self


class FiltersConfig(BaseModel):
    type_input_value: TypeInputValue

    type_value_filtering: FilterTypeValueFiltering | None = None
    filtering_values: list[str | int | float] | None = None

    type_value_threshold: FilterTypeValueThreshold | None = None
    threshold_min: int | None = None
    threshold_max: int | None = None

    max_rate: int = Field(ge=0, le=86400)
    last_unique_check: bool = False
    max_size: int = Field(ge=0)

    def _validate_filtering_values(self):
        """Validate filtering values based on input type."""
        if not (self.type_value_filtering and self.filtering_values):
            return

        if self.type_input_value == TypeInputValue.NUMBER and not all(
            isinstance(x, Real) for x in self.filtering_values
        ):
            msg = "filtering_values must be numeric for NUMBER input"
            raise ValueError(msg)
        if self.type_input_value == TypeInputValue.TEXT and not all(
            isinstance(x, str) for x in self.filtering_values
        ):
            msg = "filtering_values must be strings for TEXT input"
            raise ValueError(msg)

    def _validate_thresholds(self):
        """Validate threshold configuration for numeric input."""
        if self.type_input_value != TypeInputValue.NUMBER:
            return

        if (
            self.type_value_threshold == FilterTypeValueThreshold.MIN
            and self.threshold_min is None
        ):
            msg = "threshold_min is required for MIN threshold"
            raise ValueError(msg)

        if (
            self.type_value_threshold == FilterTypeValueThreshold.MAX
            and self.threshold_max is None
        ):
            msg = "threshold_max is required for MAX threshold"
            raise ValueError(msg)

        if self.type_value_threshold == FilterTypeValueThreshold.RANGE:
            if self.threshold_min is None or self.threshold_max is None:
                msg = "Both threshold_min and threshold_max are required for RANGE threshold"
                raise ValueError(msg)
            if self.threshold_min >= self.threshold_max:
                msg = "threshold_min must be less than threshold_max"
                raise ValueError(msg)

    def _validate_max_size(self):
        """Validate max_size against MQTT payload limit."""
        max_allowed_size = settings.pu_mqtt_max_payload_size * 1024
        if self.max_size > max_allowed_size:
            msg = f"max_size must be <= {max_allowed_size}"
            raise ValueError(msg)

    @model_validator(mode="after")
    def validate_filters(self):
        self._validate_filtering_values()
        self._validate_thresholds()
        self._validate_max_size()
        return self


class TransformationConfig(BaseModel):
    multiplication_ratio: float | None = None
    round_decimal_point: int | None = Field(default=None, ge=0, le=7)
    slice_start: int | None = None
    slice_end: int | None = None


class ProcessingPolicyConfig(BaseModel):
    policy_type: ProcessingPolicyType
    n_records_count: int | None = None
    time_window_size: int | None = None
    aggregation_functions: AggregationFunctions | None = None

    @model_validator(mode="after")
    def validate_processing(self):
        if self.policy_type == ProcessingPolicyType.N_RECORDS:
            if self.n_records_count is None:
                msg = "n_records_count is required for N_RECORDS"
                raise ValueError(msg)
            if not (0 < self.n_records_count <= 1024):
                msg = "n_records_count must be between 1 and 1024"
                raise ValueError(msg)

        if self.policy_type in [
            ProcessingPolicyType.TIME_WINDOW,
            ProcessingPolicyType.AGGREGATION,
        ]:
            if self.time_window_size is None:
                msg = "time_window_size is required"
                raise ValueError(msg)
            if self.time_window_size not in settings.pu_time_window_sizes:
                msg = f"Invalid time_window_size. Must be one of: {settings.pu_time_window_sizes}"
                raise ValueError(msg)

        if (
            self.policy_type == ProcessingPolicyType.AGGREGATION
            and self.aggregation_functions is None
        ):
            msg = "aggregation_functions is required for AGGREGATION"
            raise ValueError(msg)

        return self


class DataPipeConfig(BaseModel):
    active_period: ActivePeriod
    filters: FiltersConfig
    transformations: TransformationConfig | None = None
    processing_policy: ProcessingPolicyConfig


def format_validation_error_dict(
    e: ValidationError,
) -> list[DataPipeValidationErrorRead]:
    return [
        DataPipeValidationErrorRead(
            stage=DataPipeStage(snake_to_camel(err["loc"][0])),
            message=err["msg"],
        )
        for err in e.errors()
    ]


def is_valid_data_pipe_config(
    data: dict, is_business_validator: bool = False
) -> DataPipeConfig | list[DataPipeValidationErrorRead]:
    if data is None:
        msg = "DataPipe is None"
        raise DataPipeError(msg)

    if is_business_validator:
        try:
            return DataPipeConfig.model_validate(data)
        except ValidationError as err:
            msg = f"{len(err.errors())} validation errors for DataPipeConfig"
            raise DataPipeError(msg) from err
    else:
        try:
            DataPipeConfig.model_validate(data)
            return []
        except ValidationError as e:
            return format_validation_error_dict(e)
