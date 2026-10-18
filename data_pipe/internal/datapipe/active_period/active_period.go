package active_period

import (
	"data_pipe/internal/types"
	"time"
)

// IsActive checks if the configuration is active based on its active period
func IsActive(period *types.ActivePeriod, currentTime time.Time) bool {
	switch period.Type {
	case types.ActivePeriodTypePermanent:
		return true
	case types.ActivePeriodTypeFromDate:
		return period.Start != nil && currentTime.After(*period.Start)
	case types.ActivePeriodTypeToDate:
		return period.End != nil && currentTime.Before(*period.End)
	case types.ActivePeriodTypeDateRange:
		return period.Start != nil && period.End != nil && currentTime.After(*period.Start) && currentTime.Before(*period.End)
	default:
		return false
	}
}
