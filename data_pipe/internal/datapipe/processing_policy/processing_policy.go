package processing_policy

import (
	"context"
	"fmt"
	"time"

	"data_pipe/internal/types"

	"github.com/google/uuid"
)

// ProcessingPolicy handles message processing based on policy type
type ProcessingPolicy struct {
	bufferFactory *BufferFactory
	buffers       map[types.ProcessingPolicyType]Buffer
	ctx           context.Context
}

// NewProcessingPolicy creates a new processing policy handler
func NewProcessingPolicy(bufferFactory *BufferFactory) *ProcessingPolicy {
	return &ProcessingPolicy{
		bufferFactory: bufferFactory,
		buffers:       make(map[types.ProcessingPolicyType]Buffer),
	}
}

// Start starts all buffers
func (p *ProcessingPolicy) Start(ctx context.Context) {
	p.ctx = ctx
}

// Stop stops all buffers
func (p *ProcessingPolicy) Stop() {
	for _, buffer := range p.buffers {
		buffer.Stop()
	}
}

// ApplyProcessingPolicy applies the processing policy based on its type
func (p *ProcessingPolicy) ApplyProcessingPolicy(
	ctx context.Context,
	nodeUUID uuid.UUID,
	value string,
	currentTime time.Time,
	policy types.ProcessingPolicyConfig,
) error {
	buffer, exists := p.buffers[policy.PolicyType]
	if !exists {
		buffer = p.bufferFactory.GetBuffer(policy.PolicyType)
		if buffer == nil {
			return fmt.Errorf("no buffer available for policy type: %s", policy.PolicyType)
		}
		p.buffers[policy.PolicyType] = buffer
		buffer.Start(p.ctx)
	}

	switch policy.PolicyType {
	case types.ProcessingPolicyTypeLastValue:
		return buffer.Add(ctx, nodeUUID, value, currentTime)

	case types.ProcessingPolicyTypeNRecords:
		return buffer.Add(ctx, nodeUUID, value, currentTime)

	case types.ProcessingPolicyTypeTimeWindow:
		return buffer.Add(ctx, nodeUUID, value, currentTime)

	case types.ProcessingPolicyTypeAggregation:
		return buffer.Add(ctx, nodeUUID, value, currentTime)

	default:
		return fmt.Errorf("unknown processing policy type: %s", policy.PolicyType)
	}
}
