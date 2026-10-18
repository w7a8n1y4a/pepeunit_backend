package processing_policy

import (
	"context"
	"fmt"
	"math"
	"strconv"
	"sync"
	"time"

	"data_pipe/internal/database"
	"data_pipe/internal/logging"
	"data_pipe/internal/types"

	"github.com/google/uuid"
)

// AggregationEntry represents a single entry in the aggregation buffer
type AggregationEntry struct {
	State           float64
	UpdateTime      time.Time
	AggregationType string
}

// AggregationBuffer accumulates messages and periodically flushes them to the database
type AggregationBuffer struct {
	mu            sync.Mutex
	updates       map[uuid.UUID]map[string]*AggregationWindow // map[nodeUUID]map[windowKey]*AggregationWindow
	flushInterval time.Duration
	maxSize       int
	clickhouseDB  *database.ClickHouseDB
	stopCh        chan struct{}
	policy        *types.ProcessingPolicyConfig
}

// AggregationWindow represents a time window for aggregation
type AggregationWindow struct {
	StartTime     time.Time
	EndTime       time.Time
	Values        []float64
	Sum           float64
	Count         int64
	Min           float64
	Max           float64
	LastFlushTime time.Time
}

// NewAggregationBuffer creates a new aggregation buffer
func NewAggregationBuffer(clickhouseDB *database.ClickHouseDB, flushInterval time.Duration, maxSize int) *AggregationBuffer {
	return &AggregationBuffer{
		updates:       make(map[uuid.UUID]map[string]*AggregationWindow),
		flushInterval: flushInterval,
		maxSize:       maxSize,
		clickhouseDB:  clickhouseDB,
		stopCh:        make(chan struct{}),
	}
}

// Start begins the periodic flushing of the buffer
func (b *AggregationBuffer) Start(ctx context.Context) {
	go func() {
		ticker := time.NewTicker(b.flushInterval)
		defer ticker.Stop()

		for {
			select {
			case <-ticker.C:
				if err := b.Flush(ctx); err != nil {
					// TODO: Add proper error handling/logging
					fmt.Printf("Failed to flush buffer: %v\n", err)
				}
			case <-b.stopCh:
				return
			case <-ctx.Done():
				return
			}
		}
	}()
}

// Stop stops the buffer's periodic flushing
func (b *AggregationBuffer) Stop() {
	close(b.stopCh)
}

// getWindowKey returns a key for the window based on the time and window size
func getWindowKey(t time.Time, windowSize int) string {
	// Calculate the start of the window
	windowStart := t.Truncate(time.Duration(windowSize) * time.Second)
	return windowStart.Format(time.RFC3339)
}

// getWindowTimes returns the start and end times for a window
func getWindowTimes(t time.Time, windowSize int) (time.Time, time.Time) {
	windowStart := t.Truncate(time.Duration(windowSize) * time.Second)
	windowEnd := windowStart.Add(time.Duration(windowSize) * time.Second)
	return windowStart, windowEnd
}

// Add adds a message to the buffer
func (b *AggregationBuffer) Add(ctx context.Context, uuid uuid.UUID, state string, updateTime time.Time) error {
	// Get the policy config from the context
	policy, ok := ctx.Value("policy").(types.ProcessingPolicyConfig)
	if !ok {
		return fmt.Errorf("policy config not found in context")
	}

	if policy.AggregationFunctions == nil {
		return fmt.Errorf("aggregation functions not specified in policy")
	}

	if policy.TimeWindowSize == nil {
		return fmt.Errorf("time window size not specified in policy")
	}

	// Store policy in buffer
	b.mu.Lock()
	b.policy = &policy
	b.mu.Unlock()

	// Convert state string to float64
	stateFloat, err := strconv.ParseFloat(state, 64)
	if err != nil {
		return fmt.Errorf("failed to parse state as float64: %w", err)
	}

	// Get window key for the current time
	windowKey := getWindowKey(updateTime, *policy.TimeWindowSize)

	b.mu.Lock()
	defer b.mu.Unlock()

	// Initialize node's windows map if it doesn't exist
	if _, exists := b.updates[uuid]; !exists {
		b.updates[uuid] = make(map[string]*AggregationWindow)
	}

	// Get or create window
	window, exists := b.updates[uuid][windowKey]
	if !exists {
		startTime, endTime := getWindowTimes(updateTime, *policy.TimeWindowSize)
		window = &AggregationWindow{
			StartTime:     startTime,
			EndTime:       endTime,
			Values:        make([]float64, 0),
			Sum:           0,
			Count:         0,
			Min:           math.MaxFloat64,
			Max:           -math.MaxFloat64,
			LastFlushTime: time.Time{},
		}
		b.updates[uuid][windowKey] = window
	}

	// Update window statistics
	window.Values = append(window.Values, stateFloat)
	window.Sum += stateFloat
	window.Count++
	if stateFloat < window.Min {
		window.Min = stateFloat
	}
	if stateFloat > window.Max {
		window.Max = stateFloat
	}

	// Check if we need to flush
	if window.EndTime.Before(time.Now()) {
		return b.Flush(ctx)
	}

	return nil
}

// calculateAggregation calculates the aggregated value based on the aggregation type
func calculateAggregation(window *AggregationWindow, aggType string) float64 {
	switch aggType {
	case string(types.AggregationFunctionsAvg):
		if window.Count == 0 {
			return 0
		}
		return window.Sum / float64(window.Count)
	case string(types.AggregationFunctionsMin):
		if window.Count == 0 {
			return 0
		}
		return window.Min
	case string(types.AggregationFunctionsMax):
		if window.Count == 0 {
			return 0
		}
		return window.Max
	case string(types.AggregationFunctionsSum):
		return window.Sum
	default:
		return 0
	}
}

// Flush writes all buffered messages to the database
func (b *AggregationBuffer) Flush(ctx context.Context) error {
	b.mu.Lock()
	if len(b.updates) == 0 {
		b.mu.Unlock()
		return nil
	}

	// Create a copy of updates to work with
	updatesCopy := make(map[uuid.UUID]map[string]*AggregationWindow, len(b.updates))
	for nodeUUID, windows := range b.updates {
		updatesCopy[nodeUUID] = make(map[string]*AggregationWindow, len(windows))
		for key, window := range windows {
			// Only copy windows that are ready to be flushed
			if window.EndTime.Before(time.Now()) {
				updatesCopy[nodeUUID][key] = window
				delete(b.updates[nodeUUID], key)
			}
		}
		// Clean up empty node maps
		if len(b.updates[nodeUUID]) == 0 {
			delete(b.updates, nodeUUID)
		}
	}
	b.mu.Unlock()

	// Count total entries for logging
	totalEntries := 0
	for _, windows := range updatesCopy {
		totalEntries += len(windows)
	}
	if totalEntries == 0 {
		return nil
	}
	logging.Infof("Sending %d Aggregation entries to ClickHouse", totalEntries)

	// Get policy from buffer
	b.mu.Lock()
	policy := b.policy
	b.mu.Unlock()

	if policy == nil || policy.TimeWindowSize == nil || policy.AggregationFunctions == nil {
		return fmt.Errorf("invalid policy configuration")
	}

	// Convert updates to AggregationEntry slice
	entries := make([]database.AggregationEntry, 0, totalEntries)
	for nodeUUID, windows := range updatesCopy {
		for _, window := range windows {
			// Calculate aggregated value
			aggregatedValue := calculateAggregation(window, string(*policy.AggregationFunctions))

			entries = append(entries, database.AggregationEntry{
				UnitNodeUUID:        nodeUUID,
				State:               aggregatedValue,
				AggregationType:     string(*policy.AggregationFunctions),
				TimeWindowSize:      uint32(*policy.TimeWindowSize),
				CreateDateTime:      time.Now(),
				StartWindowDateTime: window.StartTime,
				EndWindowDateTime:   window.EndTime,
			})
		}
	}

	if err := b.clickhouseDB.BulkCreateAggregationEntries(ctx, entries); err != nil {
		return fmt.Errorf("failed to bulk create aggregation entries: %w", err)
	}

	return nil
}
