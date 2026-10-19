package datapipe

import (
	"context"
	"encoding/json"
	"fmt"
	"sync"
	"time"

	"data_pipe/internal/config"
	"data_pipe/internal/database"
	"data_pipe/internal/logging"
	"data_pipe/internal/mqtt_client"
	"data_pipe/internal/types"

	"github.com/google/uuid"
	"github.com/redis/go-redis/v9"
)

type storedNodeConfig struct {
	raw         string
	unitUUID    uuid.UUID
	creatorUUID uuid.UUID
	topicName   string
	unitName    string
}

// NodeTarget is who and where a data pipe alert belongs
type NodeTarget struct {
	UnitUUID    uuid.UUID
	CreatorUUID uuid.UUID
	TopicName   string
	UnitName    string
}

// DataPipeConfigs stores and manages DataPipe configurations for nodes
type DataPipeConfigs struct {
	mu      sync.RWMutex
	configs map[string]storedNodeConfig
	cfg     *config.Config
}

// NewDataPipeConfigs creates a new DataPipeConfigs instance
func NewDataPipeConfigs(cfg *config.Config) *DataPipeConfigs {
	return &DataPipeConfigs{
		configs: make(map[string]storedNodeConfig),
		cfg:     cfg,
	}
}

// Get retrieves a node's configuration together with the unit that owns the node
func (c *DataPipeConfigs) Get(ioUUID string) (types.DataPipeConfig, NodeTarget, bool) {
	c.mu.RLock()
	defer c.mu.RUnlock()
	stored, exists := c.configs[ioUUID]
	if !exists {
		return types.DataPipeConfig{}, NodeTarget{}, false
	}

	var config types.DataPipeConfig
	if err := json.Unmarshal([]byte(stored.raw), &config); err != nil {
		return types.DataPipeConfig{}, NodeTarget{}, false
	}
	return config, NodeTarget{
		UnitUUID:    stored.unitUUID,
		CreatorUUID: stored.creatorUUID,
		TopicName:   stored.topicName,
		UnitName:    stored.unitName,
	}, true
}

// LoadNodeConfigs loads active node configurations from PostgreSQL
func (c *DataPipeConfigs) LoadNodeConfigs(ctx context.Context, postgresDB *database.PostgresDB) error {
	nodes, err := postgresDB.GetActiveUnitIOs(ctx)
	if err != nil {
		return fmt.Errorf("failed to get active unit IO: %w", err)
	}

	c.mu.Lock()
	defer c.mu.Unlock()

	// Create a map of existing configs for quick lookup
	existingConfigs := make(map[string]struct{})
	for uuid := range c.configs {
		existingConfigs[uuid] = struct{}{}
	}

	// Update configs and track which ones are still active
	activeConfigs := make(map[string]struct{})
	for _, node := range nodes {
		activeConfigs[node.UUID.String()] = struct{}{}
		if node.DataPipeYML != nil {
			c.configs[node.UUID.String()] = storedNodeConfig{
				raw:         *node.DataPipeYML,
				unitUUID:    node.UnitUUID,
				creatorUUID: node.CreatorUUID,
				topicName:   node.TopicName,
				unitName:    node.UnitName,
			}
		}
	}

	// Remove configs for nodes that are no longer active
	for uuid := range existingConfigs {
		if _, active := activeConfigs[uuid]; !active {
			delete(c.configs, uuid)
		}
	}

	return nil
}

// StartConfigSync starts background processes for configuration synchronization
func (c *DataPipeConfigs) StartConfigSync(ctx context.Context, postgresDB *database.PostgresDB, redisDB *database.RedisDB, mqttClient *mqtt_client.MQTTClient) {
	// Start periodic sync
	go func() {
		ticker := time.NewTicker(time.Duration(c.cfg.ConfigSyncInterval) * time.Second)
		defer ticker.Stop()

		logging.Infof("Success Config Update periodic gorutine start")

		for {
			select {
			case <-ctx.Done():
				return
			case <-ticker.C:
				logging.Infof("Run gorutine update configs by main timer")
				if err := c.LoadNodeConfigs(ctx, postgresDB); err != nil {
					logging.Errorf("Failed to sync configurations by Gorutine: %v", err)
				}
			}
		}
	}()

	// Start Redis stream processing
	go func() {
		lastID := "$" // Start from the latest message

		// Create a buffer for topics
		topicBuffer := make([]string, 0)
		bufferSize := 0
		stopCh := make(chan struct{})

		// Start timer goroutine
		go func() {
			ticker := time.NewTicker(time.Duration(c.cfg.BufferFlushInterval) * time.Second)
			defer ticker.Stop()

			for {
				select {
				case <-ticker.C:
					if bufferSize > 0 {
						logging.Infof("Run update configs by Redis buffer timer")
						if err := c.LoadNodeConfigs(ctx, postgresDB); err != nil {
							logging.Errorf("Failed to update configurations: %v", err)
						}
						topicBuffer = make([]string, 0)
						bufferSize = 0
					}
				case <-stopCh:
					return
				case <-ctx.Done():
					return
				}
			}
		}()

		for {
			select {
			case <-ctx.Done():
				close(stopCh)
				logging.Infof("Redis stream processing goroutine received context cancellation")
				return
			default:
				messages, err := redisDB.ReadStream(ctx, "backend_data_pipe_nodes", lastID)
				if err != nil {
					if err != redis.Nil {
						logging.Errorf("Error reading from Redis stream: %v", err)
					}
					continue
				}

				// Process messages
				for _, message := range messages {
					lastID = message.ID
					values := message.Values

					if unitIOData, ok := values["unit_io_data"].(string); ok {
						var nodeData map[string]interface{}
						if err := json.Unmarshal([]byte(unitIOData), &nodeData); err != nil {
							logging.Errorf("Error parsing unit_io_data JSON: %v", err)
							continue
						}

						if topic, ok := nodeData["topic_name"].(string); ok {
							// Add topic to buffer
							topicBuffer = append(topicBuffer, topic)
							bufferSize++

							// Check if we need to flush based on buffer size
							if bufferSize >= c.cfg.BufferMaxSize {
								logging.Infof("Run update configs by Redis buffer size")
								if err := c.LoadNodeConfigs(ctx, postgresDB); err != nil {
									logging.Errorf("Failed to update configurations: %v", err)
								}
								topicBuffer = make([]string, 0)
								bufferSize = 0
							}
						}
					}
				}
			}
		}
	}()
}
