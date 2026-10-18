package filters

import (
	"data_pipe/internal/types"
	"strconv"
	"time"
)

// ApplyFilters applies filtering rules to the input value
func ApplyFilters(value string, config types.FiltersConfig, lastMessageTime time.Time, lastValue string) bool {
	if RejectedByList(value, config.TypeValueFiltering, config.FilteringValues, config.TypeInputValue) {
		return false
	}

	if RejectedByThreshold(value, config.TypeValueThreshold, config.ThresholdMin, config.ThresholdMax) {
		return false
	}

	// Apply rate limiting
	if config.MaxRate > 0 {
		timeSinceLastMessage := time.Since(lastMessageTime)
		if timeSinceLastMessage < time.Duration(config.MaxRate)*time.Second {
			return false
		}
	}

	// Apply size limit
	if config.MaxSize > 0 && len(value) > config.MaxSize {
		return false
	}

	// Apply uniqueness check
	if config.LastUniqueCheck && value == lastValue {
		return false
	}

	return true
}

// RejectedByList reports whether the list rule would drop the value.
// WhiteList drops a value outside the list, BlackList drops a value inside it.
// Comparison follows typeInput the same way as the rest of the pipe.
func RejectedByList(value string, typeFiltering *types.FilterTypeValueFiltering, list []interface{}, typeInput types.TypeInputValue) bool {
	if typeFiltering == nil {
		return false
	}
	inList := IsInList(value, list, typeInput)
	switch *typeFiltering {
	case types.FilterTypeValueFilteringWhiteList:
		return !inList
	case types.FilterTypeValueFilteringBlackList:
		return inList
	}
	return false
}

// RejectedByThreshold reports whether the threshold rule would drop the value.
// Min drops below ThresholdMin, Max above ThresholdMax, Range outside both.
// A value that is not a number is left alone, same as ApplyFilters.
func RejectedByThreshold(value string, typeThreshold *types.FilterTypeValueThreshold, thresholdMin *int, thresholdMax *int) bool {
	if typeThreshold == nil {
		return false
	}
	number, err := strconv.ParseFloat(value, 64)
	if err != nil {
		return false
	}
	switch *typeThreshold {
	case types.FilterTypeValueThresholdMin:
		return thresholdMin != nil && number < float64(*thresholdMin)
	case types.FilterTypeValueThresholdMax:
		return thresholdMax != nil && number > float64(*thresholdMax)
	case types.FilterTypeValueThresholdRange:
		return (thresholdMin != nil && number < float64(*thresholdMin)) ||
			(thresholdMax != nil && number > float64(*thresholdMax))
	}
	return false
}

// IsInList checks if a value is in the list of values, comparing according to the input type
func IsInList(value string, list []interface{}, typeInput types.TypeInputValue) bool {
	for _, v := range list {
		switch typeInput {
		case types.TypeInputValueText:
			if v == value {
				return true
			}
		case types.TypeInputValueNumber:
			if num, err := strconv.ParseFloat(value, 64); err == nil && num == v {
				return true
			}
		}
	}
	return false
}
