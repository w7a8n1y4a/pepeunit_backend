package alerts

import (
	"encoding/json"
	"time"

	"data_pipe/internal/apperr"
	"data_pipe/internal/database"
	"data_pipe/internal/datapipe/filters"
	"data_pipe/internal/types"

	"github.com/google/uuid"
)

const TypeDataPipeAlert = "DataPipeAlert"

// minFrequencySeconds is the shortest gap between two alerts of one node
const minFrequencySeconds = 10

// State is the alert state of a single node
type State struct {
	// Streak counts violations in a row, it is reset by a normal value
	Streak int
	// LastAlert is the time of the last published alert
	LastAlert time.Time
}

// Violation tells which alert rules the value matched.
// CatchAll is set when the config has neither a list nor a threshold.
type Violation struct {
	Filtering bool
	Threshold bool
	CatchAll  bool
}

// Any reports whether the value should raise an alert
func (v Violation) Any() bool {
	return v.Filtering || v.Threshold || v.CatchAll
}

// Evaluate checks the value against the alert config and reports which rules
// matched when an alert must be published, together with the next state.
//
// An alert is due after ConsecutiveCount matches in a row and then again
// while the value keeps matching, at most once per MaxFrequency seconds.
// MaxFrequency below 10 seconds is raised to 10.
// Evaluate runs on the value that passed filters and transformations, so the
// filters (max_rate, last_unique_check) also decide which values are counted.
func Evaluate(value string, config *types.AlertsConfig, typeInput types.TypeInputValue, state State, now time.Time) (Violation, State) {
	if !config.IsEnabled {
		return Violation{}, state
	}

	violation := check(value, config, typeInput)
	if !violation.Any() {
		state.Streak = 0
		return Violation{}, state
	}

	if state.Streak < config.ConsecutiveCount {
		state.Streak++
	}
	if state.Streak < config.ConsecutiveCount {
		return Violation{}, state
	}

	frequency := config.MaxFrequency
	if frequency < minFrequencySeconds {
		frequency = minFrequencySeconds
	}
	if !state.LastAlert.IsZero() && now.Sub(state.LastAlert) < time.Duration(frequency)*time.Second {
		return Violation{}, state
	}
	state.LastAlert = now
	return violation, state
}

// check applies the same list and threshold acceptance as the filters stage.
// A value matches WhiteList when it is in the list and BlackList when it is
// absent. Min matches at or above the minimum, Max at or below the maximum,
// Range inside both bounds. Both rules must match when both are set. With
// neither rule set, every value matches.
// typeInput comes from filters.type_input_value, so a Number rule is ignored
// for Text the same way transformations skip number-only steps.
func check(value string, config *types.AlertsConfig, typeInput types.TypeInputValue) Violation {
	listOn := config.TypeValueFiltering != nil
	thresholdOn := typeInput == types.TypeInputValueNumber && config.TypeValueThreshold != nil
	if !listOn && !thresholdOn {
		return Violation{CatchAll: true}
	}

	matchedList := listOn && !filters.RejectedByList(
		value, config.TypeValueFiltering, config.FilteringValues, typeInput,
	)
	matchedThreshold := thresholdOn && !filters.RejectedByThreshold(
		value, config.TypeValueThreshold, config.ThresholdMin, config.ThresholdMax,
	)
	if listOn && thresholdOn {
		if matchedList && matchedThreshold {
			return Violation{Filtering: true, Threshold: true}
		}
		return Violation{}
	}
	if matchedList {
		return Violation{Filtering: true}
	}
	if matchedThreshold {
		return Violation{Threshold: true}
	}
	return Violation{}
}

// Target is the node a produced alert is addressed to
type Target struct {
	UnitUUID    string
	CreatorUUID string
	TopicName   string
	UnitName    string
}

// Build is one unprocessed notifications row. Data is the raw JSON payload,
// typed later by the backend. Only the violated rules are present.
func Build(ioUUID string, target Target, value string, config *types.AlertsConfig, violation Violation) (database.Notification, error) {
	userUUID, err := uuid.Parse(target.CreatorUUID)
	if err != nil {
		return database.Notification{}, apperr.Wrap(apperr.AlertUserUUID, err, "alert user uuid")
	}
	data := map[string]interface{}{
		"unit_io_uuid": ioUUID,
		"unit_uuid":    target.UnitUUID,
		"unit_name":    target.UnitName,
		"topic_name":   target.TopicName,
		"value":        value,
	}
	if violation.Filtering && config.TypeValueFiltering != nil {
		data["type_value_filtering"] = string(*config.TypeValueFiltering)
		data["filtering_values"] = config.FilteringValues
	}
	if violation.Threshold && config.TypeValueThreshold != nil {
		data["type_value_threshold"] = string(*config.TypeValueThreshold)
		if config.ThresholdMin != nil {
			data["threshold_min"] = *config.ThresholdMin
		}
		if config.ThresholdMax != nil {
			data["threshold_max"] = *config.ThresholdMax
		}
	}
	encoded, err := json.Marshal(data)
	if err != nil {
		return database.Notification{}, apperr.Wrap(apperr.AlertPayload, err, "alert payload")
	}
	return database.Notification{
		UUID:           uuid.New(),
		CreateDatetime: time.Now().UTC(),
		Type:           TypeDataPipeAlert,
		Data:           encoded,
		UserUUID:       userUUID,
	}, nil
}
