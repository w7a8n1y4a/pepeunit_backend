package processing_policy

import (
	"context"
	"time"

	"data_pipe/internal/database"
	"data_pipe/internal/types"

	"github.com/google/uuid"
)

// Buffer defines the interface for message buffers
type Buffer interface {
	Start(ctx context.Context)
	Stop()
	Add(ctx context.Context, uuid uuid.UUID, state string, updateTime time.Time) error
	Flush(ctx context.Context) error
}

// BufferFactory creates buffers based on policy type
type BufferFactory struct {
	db            *database.PostgresDB
	clickhouseDB  *database.ClickHouseDB
	flushInterval time.Duration
	maxSize       int
}

// NewBufferFactory creates a new buffer factory
func NewBufferFactory(db *database.PostgresDB, clickhouseDB *database.ClickHouseDB, flushInterval time.Duration, maxSize int) *BufferFactory {
	return &BufferFactory{
		db:            db,
		clickhouseDB:  clickhouseDB,
		flushInterval: flushInterval,
		maxSize:       maxSize,
	}
}

// GetBuffer returns a buffer for the given policy type
func (f *BufferFactory) GetBuffer(policyType types.ProcessingPolicyType) Buffer {
	switch policyType {
	case types.ProcessingPolicyTypeLastValue:
		return NewMessageBuffer(f.db, f.flushInterval, f.maxSize)
	case types.ProcessingPolicyTypeNRecords:
		return NewNRecordsBuffer(f.clickhouseDB, f.flushInterval, f.maxSize)
	case types.ProcessingPolicyTypeTimeWindow:
		return NewTimeWindowBuffer(f.clickhouseDB, f.flushInterval, f.maxSize)
	case types.ProcessingPolicyTypeAggregation:
		return NewAggregationBuffer(f.clickhouseDB, f.flushInterval, f.maxSize)
	default:
		return nil
	}
}
