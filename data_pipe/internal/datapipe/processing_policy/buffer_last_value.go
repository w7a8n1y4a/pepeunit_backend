package processing_policy

import (
	"context"
	"fmt"
	"sync"
	"time"

	"data_pipe/internal/database"
	"data_pipe/internal/logging"

	"github.com/google/uuid"
)

// LastValueBuffer accumulates messages and periodically flushes them to the database
type LastValueBuffer struct {
	mu      sync.Mutex
	updates map[uuid.UUID]struct {
		State      string
		UpdateTime time.Time
	}
	flushInterval time.Duration
	maxSize       int
	db            *database.PostgresDB
	stopCh        chan struct{}
}

// NewMessageBuffer creates a new last value buffer
func NewMessageBuffer(db *database.PostgresDB, flushInterval time.Duration, maxSize int) *LastValueBuffer {
	return &LastValueBuffer{
		updates: make(map[uuid.UUID]struct {
			State      string
			UpdateTime time.Time
		}),
		flushInterval: flushInterval,
		maxSize:       maxSize,
		db:            db,
		stopCh:        make(chan struct{}),
	}
}

// Start begins the periodic flushing of the buffer
func (b *LastValueBuffer) Start(ctx context.Context) {
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
func (b *LastValueBuffer) Stop() {
	close(b.stopCh)
}

// Add adds a message to the buffer
func (b *LastValueBuffer) Add(ctx context.Context, uuid uuid.UUID, state string, updateTime time.Time) error {
	b.mu.Lock()
	defer b.mu.Unlock()

	b.updates[uuid] = struct {
		State      string
		UpdateTime time.Time
	}{
		State:      state,
		UpdateTime: updateTime,
	}

	if len(b.updates) >= b.maxSize {
		return b.Flush(ctx)
	}

	return nil
}

// Flush writes all buffered messages to the database
func (b *LastValueBuffer) Flush(ctx context.Context) error {
	b.mu.Lock()
	defer b.mu.Unlock()

	if len(b.updates) == 0 {
		return nil
	}

	logging.Infof("Send values for %v nodes to Postgres", len(b.updates))

	if err := b.db.BulkUpdateUnitIOStates(ctx, b.updates); err != nil {
		return fmt.Errorf("failed to bulk update unit IO states: %w", err)
	}

	// Clear the buffer after successful flush
	b.updates = make(map[uuid.UUID]struct {
		State      string
		UpdateTime time.Time
	})

	return nil
}
