package processing_policy

import (
	"context"
	"fmt"
	"sync"
	"time"

	"data_pipe/internal/database"
	"data_pipe/internal/logging"
	"data_pipe/internal/types"

	"github.com/google/uuid"
)

// TimeWindowEntry represents a single entry in the time window
type TimeWindowEntry struct {
	State              string
	UpdateTime         time.Time
	ExpirationDateTime time.Time
	TypeInputValue     types.TypeInputValue
}

// TimeWindowBuffer accumulates messages and periodically flushes them to the database
type TimeWindowBuffer struct {
	mu            sync.Mutex
	updates       map[uuid.UUID][]TimeWindowEntry
	flushInterval time.Duration
	maxSize       int
	clickhouseDB  *database.ClickHouseDB
	stopCh        chan struct{}
}

// NewTimeWindowBuffer creates a new time window buffer
func NewTimeWindowBuffer(clickhouseDB *database.ClickHouseDB, flushInterval time.Duration, maxSize int) *TimeWindowBuffer {
	return &TimeWindowBuffer{
		updates:       make(map[uuid.UUID][]TimeWindowEntry),
		flushInterval: flushInterval,
		maxSize:       maxSize,
		clickhouseDB:  clickhouseDB,
		stopCh:        make(chan struct{}),
	}
}

// Start begins the periodic flushing of the buffer
func (b *TimeWindowBuffer) Start(ctx context.Context) {
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
func (b *TimeWindowBuffer) Stop() {
	close(b.stopCh)
}

// Add adds a message to the buffer
func (b *TimeWindowBuffer) Add(ctx context.Context, uuid uuid.UUID, state string, updateTime time.Time) error {
	// Get the policy config from the context
	policy, ok := ctx.Value("policy").(types.ProcessingPolicyConfig)
	if !ok {
		return fmt.Errorf("policy config not found in context")
	}

	if policy.TimeWindowSize == nil {
		return fmt.Errorf("time window size not specified in policy")
	}

	// Get filters config from context
	filters, ok := ctx.Value("filters").(types.FiltersConfig)
	if !ok {
		return fmt.Errorf("filters config not found in context")
	}

	// Calculate expiration time based on the time window size
	expirationTime := updateTime.Add(time.Duration(*policy.TimeWindowSize) * time.Second)

	// Create new entry
	entry := TimeWindowEntry{
		State:              state,
		UpdateTime:         updateTime,
		ExpirationDateTime: expirationTime,
		TypeInputValue:     filters.TypeInputValue,
	}

	// Check if we need to flush before adding new entry
	shouldFlush := false
	b.mu.Lock()
	// Append to the node's entries
	b.updates[uuid] = append(b.updates[uuid], entry)

	// Check if we need to flush based on total number of entries across all nodes
	totalEntries := 0
	for _, entries := range b.updates {
		totalEntries += len(entries)
	}

	if totalEntries >= b.maxSize {
		shouldFlush = true
	}
	b.mu.Unlock()

	if shouldFlush {
		return b.Flush(ctx)
	}

	return nil
}

// Flush writes all buffered messages to the database
func (b *TimeWindowBuffer) Flush(ctx context.Context) error {
	// Create a copy of updates to work with
	var updatesCopy map[uuid.UUID][]TimeWindowEntry
	b.mu.Lock()
	if len(b.updates) == 0 {
		b.mu.Unlock()
		return nil
	}
	updatesCopy = make(map[uuid.UUID][]TimeWindowEntry, len(b.updates))
	for k, v := range b.updates {
		updatesCopy[k] = make([]TimeWindowEntry, len(v))
		copy(updatesCopy[k], v)
	}
	// Clear the original updates
	b.updates = make(map[uuid.UUID][]TimeWindowEntry)
	b.mu.Unlock()

	// Count total entries for logging
	totalEntries := 0
	for _, entries := range updatesCopy {
		totalEntries += len(entries)
	}
	logging.Infof("Sending %d window entries to ClickHouse", totalEntries)

	// Convert updates to WindowEntry slice
	entries := make([]database.WindowEntry, 0, totalEntries)
	for nodeUUID, nodeEntries := range updatesCopy {
		for _, entry := range nodeEntries {
			entries = append(entries, database.WindowEntry{
				UnitNodeUUID:       nodeUUID, // Use the node UUID
				State:              entry.State,
				StateType:          string(entry.TypeInputValue), // Use TypeInputValue from config
				CreateDateTime:     entry.UpdateTime,
				ExpirationDateTime: entry.ExpirationDateTime,
				Size:               uint32(len(entry.State)),
			})
		}
	}

	if err := b.clickhouseDB.BulkCreateWindowEntries(ctx, entries); err != nil {
		return fmt.Errorf("failed to bulk create window entries: %w", err)
	}

	return nil
}
