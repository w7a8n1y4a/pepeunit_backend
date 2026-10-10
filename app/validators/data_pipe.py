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


def validate_filtering_values(
    type_input_value: TypeInputValue,
    type_value_filtering: FilterTypeValueFiltering | None,
    filtering_values: list[str | int | float] | None,
):
    """Validate filtering values based on input type."""
    if not (type_value_filtering and filtering_values):
        return

    if type_input_value == TypeInputValue.NUMBER and not all(
        isinstance(x, Real) for x in filtering_values
    ):
        msg = "filtering_values must be numeric for NUMBER input"
        raise ValueError(msg)
    if type_input_value == TypeInputValue.TEXT and not all(
        isinstance(x, str) for x in filtering_values
    ):
        msg = "filtering_values must be strings for TEXT input"
        raise ValueError(msg)


def validate_thresholds(
    type_input_value: TypeInputValue,
    type_value_threshold: FilterTypeValueThreshold | None,
    threshold_min: float | None,
    threshold_max: float | None,
):
    """Validate threshold configuration for numeric input."""
    if type_input_value != TypeInputValue.NUMBER:
        return

    if (
        type_value_threshold == FilterTypeValueThreshold.MIN
        and threshold_min is None
    ):
        msg = "threshold_min is required for MIN threshold"
        raise ValueError(msg)

    if (
        type_value_threshold == FilterTypeValueThreshold.MAX
        and threshold_max is None
    ):
        msg = "threshold_max is required for MAX threshold"
        raise ValueError(msg)

    if type_value_threshold == FilterTypeValueThreshold.RANGE:
        if threshold_min is None or threshold_max is None:
            msg = "Both threshold_min and threshold_max are required for RANGE threshold"
            raise ValueError(msg)
        if threshold_min >= threshold_max:
            msg = "threshold_min must be less than threshold_max"
            raise ValueError(msg)


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

    def _validate_max_size(self):
        """Validate max_size against MQTT payload limit."""
        max_allowed_size = settings.pu_mqtt_max_payload_size * 1024
        if self.max_size > max_allowed_size:
            msg = f"max_size must be <= {max_allowed_size}"
            raise ValueError(msg)

    @model_validator(mode="after")
    def validate_filters(self):
        validate_filtering_values(
            self.type_input_value,
            self.type_value_filtering,
            self.filtering_values,
        )
        validate_thresholds(
            self.type_input_value,
            self.type_value_threshold,
            self.threshold_min,
            self.threshold_max,
        )
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


class AlertsConfig(BaseModel):
    """Alert rules use the same acceptance as filters: a value an equivalent
    filter would keep raises an alert. With neither rule set, every value
    alerts. Values are typed by filters.type_input_value, so the type
    dependent checks live in DataPipeConfig.
    """

    is_enabled: bool = True

    # WhiteList alerts on a value in the list, BlackList on a value outside it
    type_value_filtering: FilterTypeValueFiltering | None = None
    filtering_values: list[str | int | float] | None = None

    # Min alerts at or above threshold_min, Max at or below threshold_max,
    # Range inside both
    type_value_threshold: FilterTypeValueThreshold | None = None
    threshold_min: int | None = None
    threshold_max: int | None = None

    # Matches in a row required before the first alert
    consecutive_count: int = Field(default=1, ge=1, le=1024)

    # Minimum seconds between two alerts of the same node
    max_frequency: int = Field(default=10, ge=10, le=86400)

    @model_validator(mode="after")
    def validate_alerts(self):
        if self.type_value_filtering and not self.filtering_values:
            msg = f"filtering_values is required for {self.type_value_filtering.value} filtering"
            raise ValueError(msg)
        return self


class DataPipeConfig(BaseModel):
    active_period: ActivePeriod
    filters: FiltersConfig
    transformations: TransformationConfig | None = None
    processing_policy: ProcessingPolicyConfig
    alerts: AlertsConfig | None = None

    @model_validator(mode="after")
    def validate_alerts_input_type(self):
        # Errors raised here have no field location, see format_validation_error_dict
        if self.alerts is None:
            return self

        type_input_value = self.filters.type_input_value
        if (
            type_input_value == TypeInputValue.TEXT
            and self.alerts.type_value_threshold is not None
        ):
            msg = "type_value_threshold is not applicable to TEXT input"
            raise ValueError(msg)
        validate_filtering_values(
            type_input_value,
            self.alerts.type_value_filtering,
            self.alerts.filtering_values,
        )
        validate_thresholds(
            type_input_value,
            self.alerts.type_value_threshold,
            self.alerts.threshold_min,
            self.alerts.threshold_max,
        )
        return self


def format_validation_error_dict(
    e: ValidationError,
) -> list[DataPipeValidationErrorRead]:
    # The only cross stage check is alerts against filters, it has no location
    return [
        DataPipeValidationErrorRead(
            stage=DataPipeStage(snake_to_camel(err["loc"][0]))
            if err["loc"]
            else DataPipeStage.ALERTS,
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
