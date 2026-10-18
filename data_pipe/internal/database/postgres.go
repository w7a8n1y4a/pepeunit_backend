package database

import (
	"context"
	"fmt"
	"strings"
	"time"

	"data_pipe/internal/config"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

type PostgresDB struct {
	pool *pgxpool.Pool
}

func NewPostgres(connString string) (*PostgresDB, error) {
	pool, err := pgxpool.New(context.Background(), connString)
	if err != nil {
		return nil, fmt.Errorf("unable to create connection pool: %w", err)
	}

	if err := pool.Ping(context.Background()); err != nil {
		return nil, fmt.Errorf("unable to ping database: %w", err)
	}

	return &PostgresDB{pool: pool}, nil
}

func (db *PostgresDB) Close() {
	if db.pool != nil {
		db.pool.Close()
	}
}

func (db *PostgresDB) Query(ctx context.Context, query string, args ...interface{}) (pgx.Rows, error) {
	return db.pool.Query(ctx, query, args...)
}

func (db *PostgresDB) QueryRow(ctx context.Context, query string, args ...interface{}) pgx.Row {
	return db.pool.QueryRow(ctx, query, args...)
}

func (db *PostgresDB) Exec(ctx context.Context, query string, args ...interface{}) error {
	_, err := db.pool.Exec(ctx, query, args...)
	return err
}

// LoadInstanceSettings reads the data pipe columns of the single settings row.
func (db *PostgresDB) LoadInstanceSettings(ctx context.Context) (config.RuntimeSettings, error) {
	query := `
		SELECT pu_datapipe_buffer_flush_interval,
			pu_datapipe_buffer_max_size,
			pu_datapipe_config_sync_interval,
			pu_datapipe_mqtt_keepalive,
			pu_datapipe_nrecords_cleanup_interval,
			pu_ff_notification_enable,
			pu_ff_datapipe_enable,
			pu_instance_log_min_level,
			pu_instance_log_format
		FROM instance_settings
		WHERE uuid = $1`

	var settings config.RuntimeSettings
	err := db.QueryRow(ctx, query, config.InstanceSettingsUUID()).Scan(
		&settings.BufferFlushInterval,
		&settings.BufferMaxSize,
		&settings.ConfigSyncInterval,
		&settings.MQTTKeepAlive,
		&settings.NRecordsCleanupInterval,
		&settings.NotificationEnable,
		&settings.DatapipeEnable,
		&settings.LogMinLevel,
		&settings.LogFormat,
	)
	if err != nil {
		return config.RuntimeSettings{}, fmt.Errorf("failed to load instance settings: %w", err)
	}
	return settings, nil
}

type DataPipeStatus string

const (
	DataPipeStatusActive   DataPipeStatus = "Active"
	DataPipeStatusInactive DataPipeStatus = "Inactive"
	DataPipeStatusError    DataPipeStatus = "Error"
)

type UnitNode struct {
	UUID               uuid.UUID `db:"uuid"`
	Type               string    `db:"type"`
	VisibilityLevel    string    `db:"visibility_level"`
	IsRewritableInput  bool      `db:"is_rewritable_input"`
	TopicName          string    `db:"topic_name"`
	CreateDatetime     time.Time `db:"create_datetime"`
	State              *string   `db:"state"`
	LastUpdateDatetime time.Time `db:"last_update_datetime"`
	IsDataPipeActive   bool      `db:"is_data_pipe_active"`
	DataPipeYML        *string   `db:"data_pipe_yml"`
	DataPipeStatus     *string   `db:"data_pipe_status"`
	DataPipeError      *string   `db:"data_pipe_error"`
	CreatorUUID        uuid.UUID `db:"creator_uuid"`
	UnitUUID           uuid.UUID `db:"unit_uuid"`
	UnitName           string    `db:"unit_name"`
}

// GetActiveUnitNodes returns all active unit nodes
func (db *PostgresDB) GetActiveUnitNodes(ctx context.Context) ([]*UnitNode, error) {
	query := `
		SELECT n.uuid, n.type, n.visibility_level, n.is_rewritable_input, n.topic_name,
			n.create_datetime, n.state, n.last_update_datetime, n.is_data_pipe_active,
			n.data_pipe_yml, n.data_pipe_status, n.data_pipe_error, n.creator_uuid,
			n.unit_uuid, u.name
		FROM units_nodes n
		JOIN units u ON u.uuid = n.unit_uuid
		WHERE n.is_data_pipe_active = true`

	rows, err := db.Query(ctx, query)
	if err != nil {
		return nil, fmt.Errorf("failed to query active unit nodes: %w", err)
	}
	defer rows.Close()

	var nodes []*UnitNode
	for rows.Next() {
		node := &UnitNode{}
		if err := rows.Scan(
			&node.UUID, &node.Type, &node.VisibilityLevel, &node.IsRewritableInput,
			&node.TopicName, &node.CreateDatetime, &node.State, &node.LastUpdateDatetime,
			&node.IsDataPipeActive, &node.DataPipeYML, &node.DataPipeStatus,
			&node.DataPipeError, &node.CreatorUUID, &node.UnitUUID, &node.UnitName,
		); err != nil {
			return nil, fmt.Errorf("failed to scan unit node: %w", err)
		}
		nodes = append(nodes, node)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating unit nodes: %w", err)
	}

	return nodes, nil
}

// BulkUpdateUnitNodeStates updates multiple unit node states in a single query
func (db *PostgresDB) BulkUpdateUnitNodeStates(ctx context.Context, updates map[uuid.UUID]struct {
	State      string
	UpdateTime time.Time
}) error {
	if len(updates) == 0 {
		return nil
	}

	query := `
		UPDATE units_nodes AS t SET
			state = c.state,
			last_update_datetime = c.last_update_datetime::timestamp
		FROM (VALUES 
	`

	values := make([]interface{}, 0, len(updates)*3)
	valueStrings := make([]string, 0, len(updates))

	i := 1
	for uuid, update := range updates {
		valueStrings = append(valueStrings, fmt.Sprintf("($%d, $%d, $%d)", i, i+1, i+2))
		// Format time as 'YYYY-MM-DD HH:MM:SS' with explicit timestamp cast
		formattedTime := update.UpdateTime.Format("2006-01-02 15:04:05")
		values = append(values, uuid, update.State, formattedTime)
		i += 3
	}

	query += strings.Join(valueStrings, ",")
	query += `
		) AS c(uuid, state, last_update_datetime)
		WHERE t.uuid = c.uuid::uuid
	`

	_, err := db.pool.Exec(ctx, query, values...)
	if err != nil {
		return fmt.Errorf("failed to bulk update unit node states: %w", err)
	}

	return nil
}

// Notification is one unprocessed row of the notifications table.
// Data is the raw JSON payload. The backend types it later.
type Notification struct {
	UUID           uuid.UUID
	CreateDatetime time.Time
	Type           string
	Data           []byte
	UserUUID       uuid.UUID
}

// InsertNotifications writes a batch of unprocessed notifications.
func (db *PostgresDB) InsertNotifications(ctx context.Context, rows []Notification) error {
	if len(rows) == 0 {
		return nil
	}

	query := `
		INSERT INTO notifications (
			uuid, create_datetime, type, data, is_read, user_uuid, is_processed
		) VALUES `

	values := make([]interface{}, 0, len(rows)*5)
	valueStrings := make([]string, 0, len(rows))
	for i, row := range rows {
		base := i*5 + 1
		valueStrings = append(valueStrings, fmt.Sprintf(
			"($%d, $%d, $%d, $%d::jsonb, false, $%d, false)",
			base, base+1, base+2, base+3, base+4,
		))
		values = append(values, row.UUID, row.CreateDatetime, row.Type, row.Data, row.UserUUID)
	}

	query += strings.Join(valueStrings, ",")
	if err := db.Exec(ctx, query, values...); err != nil {
		return fmt.Errorf("failed to insert notifications: %w", err)
	}
	return nil
}
