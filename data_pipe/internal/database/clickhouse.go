package database

import (
	"context"
	"fmt"
	"net/url"
	"strings"
	"time"

	"github.com/ClickHouse/clickhouse-go/v2"
	"github.com/google/uuid"
)

type ClickHouseDB struct {
	conn clickhouse.Conn
}

type clickHouseTarget struct {
	addr     string
	database string
	username string
	password string
}

func parseClickHouseURL(connString string) (clickHouseTarget, error) {
	// SQLAlchemy stores clickhouse+native://. Drop the driver token.
	if strings.HasPrefix(connString, "clickhouse+") {
		rest := connString[len("clickhouse+"):]
		if schemeEnd := strings.Index(rest, "://"); schemeEnd >= 0 {
			connString = "clickhouse" + rest[schemeEnd:]
		}
	}

	parsed, err := url.Parse(connString)
	if err != nil {
		return clickHouseTarget{}, fmt.Errorf("invalid connection string: %w", err)
	}

	port := parsed.Port()
	if port == "" {
		port = "9000"
	}
	database := strings.TrimPrefix(parsed.Path, "/")
	if database == "" {
		database = "default"
	}
	password, _ := parsed.User.Password()
	return clickHouseTarget{
		addr:     fmt.Sprintf("%s:%s", parsed.Hostname(), port),
		database: database,
		username: parsed.User.Username(),
		password: password,
	}, nil
}

func NewClickHouse(connString string) (*ClickHouseDB, error) {
	target, err := parseClickHouseURL(connString)
	if err != nil {
		return nil, err
	}

	conn, err := clickhouse.Open(&clickhouse.Options{
		Addr: []string{target.addr},
		Auth: clickhouse.Auth{
			Database: target.database,
			Username: target.username,
			Password: target.password,
		},
		Settings: clickhouse.Settings{
			"max_execution_time": 60,
		},
		Debug: false,
	})
	if err != nil {
		return nil, fmt.Errorf("unable to connect to clickhouse: %w", err)
	}

	if err := conn.Ping(context.Background()); err != nil {
		return nil, fmt.Errorf("unable to ping clickhouse: %w", err)
	}

	return &ClickHouseDB{conn: conn}, nil
}

func (db *ClickHouseDB) Close() error {
	return db.conn.Close()
}

// NLastEntry represents a record for the n_last_entry table
type NLastEntry struct {
	UnitNodeUUID   uuid.UUID
	State          string
	StateType      string // "Number" or "Text"
	CreateDateTime time.Time
	MaxCount       uint32
	Size           uint32
}

// BulkCreateNLastEntries inserts multiple records into n_last_entry table
func (db *ClickHouseDB) BulkCreateNLastEntries(ctx context.Context, entries []NLastEntry) error {
	batch, err := db.conn.PrepareBatch(ctx, "INSERT INTO n_last_entry")
	if err != nil {
		return fmt.Errorf("failed to prepare batch: %w", err)
	}

	for _, entry := range entries {
		err := batch.Append(
			entry.UnitNodeUUID,
			entry.State,
			entry.StateType,
			entry.CreateDateTime,
			entry.MaxCount,
			entry.Size,
		)
		if err != nil {
			return fmt.Errorf("failed to append entry to batch: %w", err)
		}
	}

	if err := batch.Send(); err != nil {
		return fmt.Errorf("failed to send batch: %w", err)
	}

	return nil
}

// WindowEntry represents a record for the window_entry table
type WindowEntry struct {
	UnitNodeUUID       uuid.UUID
	State              string
	StateType          string // "Number" or "Text"
	CreateDateTime     time.Time
	ExpirationDateTime time.Time
	Size               uint32
}

// BulkCreateWindowEntries inserts multiple records into window_entry table
func (db *ClickHouseDB) BulkCreateWindowEntries(ctx context.Context, entries []WindowEntry) error {
	batch, err := db.conn.PrepareBatch(ctx, "INSERT INTO window_entry")
	if err != nil {
		return fmt.Errorf("failed to prepare batch: %w", err)
	}

	for _, entry := range entries {
		err := batch.Append(
			entry.UnitNodeUUID,
			entry.State,
			entry.StateType,
			entry.CreateDateTime,
			entry.ExpirationDateTime,
			entry.Size,
		)
		if err != nil {
			return fmt.Errorf("failed to append entry to batch: %w", err)
		}
	}

	if err := batch.Send(); err != nil {
		return fmt.Errorf("failed to send batch: %w", err)
	}

	return nil
}

// AggregationEntry represents a record for the aggregation_entry table
type AggregationEntry struct {
	UnitNodeUUID        uuid.UUID
	State               float64
	AggregationType     string // "Avg", "Min", "Max", "Sum"
	TimeWindowSize      uint32 // Size of the time window in seconds
	CreateDateTime      time.Time
	StartWindowDateTime time.Time
	EndWindowDateTime   time.Time
}

// BulkCreateAggregationEntries inserts multiple records into aggregation_entry table
func (db *ClickHouseDB) BulkCreateAggregationEntries(ctx context.Context, entries []AggregationEntry) error {
	batch, err := db.conn.PrepareBatch(ctx, "INSERT INTO aggregation_entry")
	if err != nil {
		return fmt.Errorf("failed to prepare batch: %w", err)
	}

	for _, entry := range entries {
		err := batch.Append(
			entry.UnitNodeUUID,
			entry.State,
			entry.AggregationType,
			entry.TimeWindowSize,
			entry.CreateDateTime,
			entry.StartWindowDateTime,
			entry.EndWindowDateTime,
		)
		if err != nil {
			return fmt.Errorf("failed to append entry to batch: %w", err)
		}
	}

	if err := batch.Send(); err != nil {
		return fmt.Errorf("failed to send batch: %w", err)
	}

	return nil
}

// CleanupNLastEntries removes entries that exceed max_count for each unit_node_uuid
func (db *ClickHouseDB) CleanupNLastEntries(ctx context.Context) error {
	query := `
		ALTER TABLE n_last_entry
		DELETE WHERE (unit_node_uuid, create_datetime) IN (
			SELECT unit_node_uuid, create_datetime
			FROM (
				SELECT
					unit_node_uuid,
					create_datetime,
					ROW_NUMBER() OVER (
						PARTITION BY unit_node_uuid
						ORDER BY create_datetime DESC
					) as row_num,
					max_count
				FROM n_last_entry
			) AS numbered_records
			WHERE row_num > max_count
		)`

	if err := db.conn.Exec(ctx, query); err != nil {
		return fmt.Errorf("failed to cleanup NLast entries: %w", err)
	}

	return nil
}
