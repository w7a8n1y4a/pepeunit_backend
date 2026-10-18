package types

import "time"

// ActivePeriodType represents the type of active period
type ActivePeriodType string

const (
	ActivePeriodTypePermanent ActivePeriodType = "Permanent"
	ActivePeriodTypeFromDate  ActivePeriodType = "FromDate"
	ActivePeriodTypeToDate    ActivePeriodType = "ToDate"
	ActivePeriodTypeDateRange ActivePeriodType = "DateRange"
)

// ActivePeriod represents the period when the configuration is active
type ActivePeriod struct {
	Type  ActivePeriodType `json:"type"`
	Start *time.Time       `json:"start,omitempty"`
	End   *time.Time       `json:"end,omitempty"`
}

// TypeInputValue represents the type of input value
type TypeInputValue string

const (
	TypeInputValueText   TypeInputValue = "Text"
	TypeInputValueNumber TypeInputValue = "Number"
)

// FilterTypeValueFiltering represents the type of filtering
type FilterTypeValueFiltering string

const (
	FilterTypeValueFilteringWhiteList FilterTypeValueFiltering = "WhiteList"
	FilterTypeValueFilteringBlackList FilterTypeValueFiltering = "BlackList"
)

// FilterTypeValueThreshold represents the type of threshold
type FilterTypeValueThreshold string

const (
	FilterTypeValueThresholdMin   FilterTypeValueThreshold = "Min"
	FilterTypeValueThresholdMax   FilterTypeValueThreshold = "Max"
	FilterTypeValueThresholdRange FilterTypeValueThreshold = "Range"
)

// FiltersConfig represents the configuration for filtering values
type FiltersConfig struct {
	TypeInputValue     TypeInputValue            `json:"type_input_value"`
	TypeValueFiltering *FilterTypeValueFiltering `json:"type_value_filtering,omitempty"`
	FilteringValues    []interface{}             `json:"filtering_values,omitempty"`
	TypeValueThreshold *FilterTypeValueThreshold `json:"type_value_threshold,omitempty"`
	ThresholdMin       *int                      `json:"threshold_min,omitempty"`
	ThresholdMax       *int                      `json:"threshold_max,omitempty"`
	MaxRate            int                       `json:"max_rate"`
	LastUniqueCheck    bool                      `json:"last_unique_check"`
	MaxSize            int                       `json:"max_size"`
}

// TransformationConfig represents the configuration for value transformations
type TransformationConfig struct {
	MultiplicationRatio *float64 `json:"multiplication_ratio,omitempty"`
	RoundDecimalPoint   *int     `json:"round_decimal_point,omitempty"`
	SliceStart          *int     `json:"slice_start,omitempty"`
	SliceEnd            *int     `json:"slice_end,omitempty"`
}

// ProcessingPolicyType represents the type of processing policy
type ProcessingPolicyType string

const (
	ProcessingPolicyTypeLastValue   ProcessingPolicyType = "LastValue"
	ProcessingPolicyTypeNRecords    ProcessingPolicyType = "NRecords"
	ProcessingPolicyTypeTimeWindow  ProcessingPolicyType = "TimeWindow"
	ProcessingPolicyTypeAggregation ProcessingPolicyType = "Aggregation"
)

// AggregationFunctions represents the type of aggregation function
type AggregationFunctions string

const (
	AggregationFunctionsAvg AggregationFunctions = "Avg"
	AggregationFunctionsMin AggregationFunctions = "Min"
	AggregationFunctionsMax AggregationFunctions = "Max"
	AggregationFunctionsSum AggregationFunctions = "Sum"
)

// ProcessingPolicyConfig represents the configuration for processing policy
type ProcessingPolicyConfig struct {
	PolicyType           ProcessingPolicyType  `json:"policy_type"`
	NRecordsCount        *int                  `json:"n_records_count,omitempty"`
	TimeWindowSize       *int                  `json:"time_window_size,omitempty"`
	AggregationFunctions *AggregationFunctions `json:"aggregation_functions,omitempty"`
}

// AlertsConfig is an optional stage that emits a notification when a value
// would pass the same list or threshold rule as the filters stage. The rules
// mirror FiltersConfig and are typed by FiltersConfig.TypeInputValue. With
// neither rule set, every value alerts.
type AlertsConfig struct {
	IsEnabled bool `json:"is_enabled"`

	// WhiteList alerts on a value in the list, BlackList on a value outside it.
	// With neither this nor TypeValueThreshold set, every value alerts.
	TypeValueFiltering *FilterTypeValueFiltering `json:"type_value_filtering,omitempty"`
	FilteringValues    []interface{}             `json:"filtering_values,omitempty"`

	// Min alerts at or above ThresholdMin, Max at or below ThresholdMax,
	// Range inside both. Same acceptance as the filters stage.
	TypeValueThreshold *FilterTypeValueThreshold `json:"type_value_threshold,omitempty"`
	ThresholdMin       *int                      `json:"threshold_min,omitempty"`
	ThresholdMax       *int                      `json:"threshold_max,omitempty"`

	// ConsecutiveCount is how many violations in a row precede the first alert
	ConsecutiveCount int `json:"consecutive_count"`

	// MaxFrequency is the minimum number of seconds between two alerts.
	// Values below 10 are treated as 10.
	MaxFrequency int `json:"max_frequency"`
}

// DataPipeConfig represents the complete configuration for data processing
type DataPipeConfig struct {
	ActivePeriod     ActivePeriod           `json:"active_period"`
	Filters          FiltersConfig          `json:"filters"`
	Transformations  *TransformationConfig  `json:"transformations,omitempty"`
	ProcessingPolicy ProcessingPolicyConfig `json:"processing_policy"`
	Alerts           *AlertsConfig          `json:"alerts,omitempty"`
}
