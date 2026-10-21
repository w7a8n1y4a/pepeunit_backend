package processing_policy

import (
	"context"
	"fmt"
	"sync"
	"time"

	"data_pipe/internal/apperr"
	"data_pipe/internal/database"
	"data_pipe/internal/logging"
	"data_pipe/internal/types"

	"github.com/google/uuid"
)

// NRecordsEntry represents a single entry in the NRecords buffer
type NRecordsEntry struct {
	State          string
	UpdateTime     time.Time
	TypeInputValue types.TypeInputValue
}

// NRecordsBuffer accumulates messages and periodically flushes them to the database
type NRecordsBuffer struct {
	mu            sync.Mutex
	updates       map[uuid.UUID][]NRecordsEntry
	flushInterval time.Duration
	maxSize       int
	clickhouseDB  *database.ClickHouseDB
	stopCh        chan struct{}
	policy        *types.ProcessingPolicyConfig
}

// NewNRecordsBuffer creates a new NRecords buffer
func NewNRecordsBuffer(clickhouseDB *database.ClickHouseDB, flushInterval time.Duration, maxSize int) *NRecordsBuffer {
	return &NRecordsBuffer{
		updates:       make(map[uuid.UUID][]NRecordsEntry),
		flushInterval: flushInterval,
		maxSize:       maxSize,
		clickhouseDB:  clickhouseDB,
		stopCh:        make(chan struct{}),
	}
}

// Start begins the periodic flushing of the buffer
func (b *NRecordsBuffer) Start(ctx context.Context) {
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
func (b *NRecordsBuffer) Stop() {
	close(b.stopCh)
}

// Add adds a message to the buffer
func (b *NRecordsBuffer) Add(ctx context.Context, uuid uuid.UUID, state string, updateTime time.Time) error {
	// Get the policy config from the context
	policy, ok := ctx.Value("policy").(types.ProcessingPolicyConfig)
	if !ok {
		return apperr.New(apperr.PolicyConfigMissing, "policy config not found in context")
	}

	if policy.NRecordsCount == nil {
		return apperr.New(apperr.NRecordsCountMissing, "NRecords count not specified in policy")
	}

	// Store policy in buffer
	b.mu.Lock()
	b.policy = &policy
	b.mu.Unlock()

	// Get filters config from context
	filters, ok := ctx.Value("filters").(types.FiltersConfig)
	if !ok {
		return apperr.New(apperr.FiltersConfigMissing, "filters config not found in context")
	}

	// Create new entry
	entry := NRecordsEntry{
		State:          state,
		UpdateTime:     updateTime,
		TypeInputValue: filters.TypeInputValue,
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
func (b *NRecordsBuffer) Flush(ctx context.Context) error {
	// Create a copy of updates to work with
	var updatesCopy map[uuid.UUID][]NRecordsEntry
	b.mu.Lock()
	if len(b.updates) == 0 {
		b.mu.Unlock()
		return nil
	}
	updatesCopy = make(map[uuid.UUID][]NRecordsEntry, len(b.updates))
	for k, v := range b.updates {
		updatesCopy[k] = make([]NRecordsEntry, len(v))
		copy(updatesCopy[k], v)
	}
	// Clear the original updates
	b.updates = make(map[uuid.UUID][]NRecordsEntry)
	b.mu.Unlock()

	// Count total entries for logging
	totalEntries := 0
	for _, entries := range updatesCopy {
		totalEntries += len(entries)
	}
	logging.Infof("Sending %d NRecords entries to ClickHouse", totalEntries)

	// Get policy from buffer
	b.mu.Lock()
	policy := b.policy
	b.mu.Unlock()

	if policy == nil || policy.NRecordsCount == nil {
		return apperr.New(apperr.NRecordsCountMissing, "NRecords count not specified in policy")
	}

	// Convert updates to NLastEntry slice
	entries := make([]database.NLastEntry, 0, totalEntries)
	for ioUUID, nodeEntries := range updatesCopy {
		for _, entry := range nodeEntries {
			entries = append(entries, database.NLastEntry{
				UnitIOUUID:     ioUUID, // Use the node UUID
				State:          entry.State,
				StateType:      string(entry.TypeInputValue), // Use TypeInputValue from config
				CreateDateTime: entry.UpdateTime,
				MaxCount:       uint32(*policy.NRecordsCount), // Use NRecordsCount from policy
				Size:           uint32(len(entry.State)),
			})
		}
	}

	if err := b.clickhouseDB.BulkCreateNLastEntries(ctx, entries); err != nil {
		return fmt.Errorf("failed to bulk create NLast entries: %w", err)
	}

	return nil
}
