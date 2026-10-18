package database

import (
	"context"
	"fmt"
	"strings"

	"data_pipe/internal/logging"

	"github.com/redis/go-redis/v9"
)

type RedisDB struct {
	client *redis.Client
}

func NewRedis(url string) (*RedisDB, error) {
	// Remove redis:// prefix
	redisURL := strings.TrimPrefix(url, "redis://")

	// Extract DB number from suffix
	dbNum := 0
	if strings.HasSuffix(redisURL, "/0") {
		redisURL = strings.TrimSuffix(redisURL, "/0")
	} else if strings.HasSuffix(redisURL, "/1") {
		redisURL = strings.TrimSuffix(redisURL, "/1")
		dbNum = 1
	} else if strings.HasSuffix(redisURL, "/2") {
		redisURL = strings.TrimSuffix(redisURL, "/2")
		dbNum = 2
	}

	client := redis.NewClient(&redis.Options{
		Addr:     redisURL,
		Password: "", // no password set
		DB:       dbNum,
	})

	// Test connection
	if err := client.Ping(context.Background()).Err(); err != nil {
		return nil, fmt.Errorf("failed to connect to Redis: %w", err)
	}

	logging.Infof("Success Connected to Redis at %s (DB: %d)", redisURL, dbNum)
	return &RedisDB{client: client}, nil
}

func (db *RedisDB) Close() {
	if db.client != nil {
		db.client.Close()
	}
}

// ReadStream reads messages from a Redis stream
func (db *RedisDB) ReadStream(ctx context.Context, streamName string, lastID string) ([]redis.XMessage, error) {
	streams, err := db.client.XRead(ctx, &redis.XReadArgs{
		Streams: []string{streamName, lastID},
		Block:   0,
	}).Result()

	if err != nil {
		return nil, fmt.Errorf("failed to read from Redis stream: %w", err)
	}

	if len(streams) == 0 {
		return nil, nil
	}

	return streams[0].Messages, nil
}

// AddStreamBatch appends messages to a Redis stream in a single round trip
func (db *RedisDB) AddStreamBatch(ctx context.Context, streamName string, batch []map[string]interface{}) error {
	if len(batch) == 0 {
		return nil
	}

	pipe := db.client.Pipeline()
	for _, values := range batch {
		pipe.XAdd(ctx, &redis.XAddArgs{
			Stream: streamName,
			Values: values,
		})
	}

	if _, err := pipe.Exec(ctx); err != nil {
		return fmt.Errorf("failed to add %d messages to Redis stream %s: %w", len(batch), streamName, err)
	}
	return nil
}
