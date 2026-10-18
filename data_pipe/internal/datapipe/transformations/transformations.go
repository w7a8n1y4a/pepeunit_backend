package transformations

import (
	"data_pipe/internal/types"
	"fmt"
	"strconv"
)

// ApplyTransformations applies configured transformations to the input value
func ApplyTransformations(value string, config *types.TransformationConfig, filtersConfig *types.FiltersConfig) (string, error) {

	if filtersConfig.TypeInputValue == types.TypeInputValueNumber {
		// Apply multiplication if configured
		if config.MultiplicationRatio != nil {
			numValue, err := strconv.ParseFloat(value, 64)
			if err != nil {
				return value, nil
			}
			value = fmt.Sprintf("%f", numValue**config.MultiplicationRatio)
		}

		// Apply rounding if configured
		if config.RoundDecimalPoint != nil {
			numValue, err := strconv.ParseFloat(value, 64)
			if err != nil {
				return value, nil
			}
			value = fmt.Sprintf("%.*f", *config.RoundDecimalPoint, numValue)
		}

	} else {
		// Apply slicing if configured
		if config.SliceStart != nil || config.SliceEnd != nil {
			length := len(value)
			start := 0
			end := length

			// Handle start index (Python-like)
			if config.SliceStart != nil {
				start = *config.SliceStart
				if start < 0 {
					start = length + start // Python: -1 means last element
				}
				if start < 0 {
					start = 0 // Python: -len-1 means first element
				}
				if start > length {
					start = length // Python: len+1 means empty slice
				}
			}

			// Handle end index (Python-like)
			if config.SliceEnd != nil {
				end = *config.SliceEnd
				if end < 0 {
					end = length + end // Python: -1 means last element
				}
				if end < 0 {
					end = 0 // Python: -len-1 means first element
				}
				if end > length {
					end = length // Python: len+1 means up to last element
				}
			}

			// Python-like slicing
			if start < end {
				value = value[start:end]
			} else {
				value = "" // Python: returns empty string if start >= end
			}
		}
	}

	return value, nil
}
