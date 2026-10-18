package alerts

import (
	"context"
	"fmt"
	"sync"
	"time"

	"data_pipe/internal/database"
	"data_pipe/internal/logging"
)

// Store is the part of Postgres the buffer writes to
type Store interface {
	InsertNotifications(ctx context.Context, rows []database.Notification) error
}

// Buffer accumulates alert rows and periodically flushes them to Postgres,
// the same way processing policy buffers flush to the databases
type Buffer struct {
	mu            sync.Mutex
	entries       []database.Notification
	flushInterval time.Duration
	maxSize       int
	store         Store
	stopCh        chan struct{}
}

// NewBuffer creates a new alert buffer
func NewBuffer(store Store, flushInterval time.Duration, maxSize int) *Buffer {
	return &Buffer{
		entries:       make([]database.Notification, 0, maxSize),
		flushInterval: flushInterval,
		maxSize:       maxSize,
		store:         store,
		stopCh:        make(chan struct{}),
	}
}

// Start begins the periodic flushing of the buffer
func (b *Buffer) Start(ctx context.Context) {
	go func() {
		ticker := time.NewTicker(b.flushInterval)
		defer ticker.Stop()

		for {
			select {
			case <-ticker.C:
				if err := b.Flush(ctx); err != nil {
					logging.Errorf("Failed to flush alert buffer: %v", err)
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
func (b *Buffer) Stop() {
	close(b.stopCh)
}

// Add adds an alert row to the buffer
func (b *Buffer) Add(ctx context.Context, row database.Notification) error {
	b.mu.Lock()
	b.entries = append(b.entries, row)
	shouldFlush := len(b.entries) >= b.maxSize
	b.mu.Unlock()

	if shouldFlush {
		return b.Flush(ctx)
	}

	return nil
}

// Flush inserts all buffered alerts into notifications
func (b *Buffer) Flush(ctx context.Context) error {
	b.mu.Lock()
	if len(b.entries) == 0 {
		b.mu.Unlock()
		return nil
	}
	batch := b.entries
	b.entries = make([]database.Notification, 0, b.maxSize)
	b.mu.Unlock()

	logging.Infof("Send %d alerts to notifications", len(batch))

	if err := b.store.InsertNotifications(ctx, batch); err != nil {
		return fmt.Errorf("failed to insert alerts: %w", err)
	}

	return nil
}
