package config

import (
	"context"
	"strings"
	"time"

	"data_pipe/internal/apperr"
	"data_pipe/internal/logging"

	"github.com/caarlos0/env"
	"github.com/joho/godotenv"
)

// RefreshInterval matches the backend runtime cache.
// Both processes notice an instance_settings change on the same cadence.
const RefreshInterval = 5 * time.Second

// instanceSettingsUUID is the single row the backend writes.
const instanceSettingsUUID = "00000000-0000-4000-8000-000000000001"

// RuntimeSettings are the data pipe columns of instance_settings.
// The backend stores them in Postgres. Env files no longer carry them.
type RuntimeSettings struct {
	BufferFlushInterval     int
	BufferMaxSize           int
	ConfigSyncInterval      int
	MQTTKeepAlive           int
	NRecordsCleanupInterval int
	NotificationEnable      bool
	DatapipeEnable          bool
	LogMinLevel             string
	LogFormat               string
}

// SamePipe reports whether the settings that require a process restart match.
// Log level and format are applied in place.
func (s RuntimeSettings) SamePipe(other RuntimeSettings) bool {
	s.LogMinLevel = ""
	s.LogFormat = ""
	other.LogMinLevel = ""
	other.LogFormat = ""
	return s == other
}

// Config is the process configuration.
// Connection values come from the environment, after .env is loaded
// without overriding variables that are already set.
// RuntimeSettings come from Postgres.
type Config struct {
	Domain                  string
	SecretKey               string
	PostgresURL             string
	ClickHouseURL           string
	RedisURL                string
	MQTTHost                string
	MQTTPort                int
	MQTTKeepAlive           int
	ConfigSyncInterval      int
	NRecordsCleanupInterval int
	BufferFlushInterval     int
	BufferMaxSize           int
	NotificationEnable      bool
	DatapipeEnable          bool
	LogMinLevel             string
	LogFormat               string
}

type envSettings struct {
	Domain        string `env:"PU_DOMAIN,required"`
	SecretKey     string `env:"PU_SECRET_KEY,required"`
	PostgresURL   string `env:"PU_SQLALCHEMY_DATABASE_URL,required"`
	ClickHouseURL string `env:"PU_CLICKHOUSE_DATABASE_URL,required"`
	RedisURL      string `env:"PU_REDIS_URL" envDefault:"redis://redis:6379/0"`
	MQTTHost      string `env:"PU_MQTT_HOST,required"`
	MQTTPort      int    `env:"PU_MQTT_PORT" envDefault:"1883"`
}

// LoadEnv reads .env and then the process environment.
// A variable that is already set wins over the file, same as the backend.
func LoadEnv() (*Config, error) {
	_ = godotenv.Load()

	parsed := &envSettings{}
	if err := env.Parse(parsed); err != nil {
		return nil, err
	}

	cfg := &Config{
		Domain:        parsed.Domain,
		SecretKey:     parsed.SecretKey,
		PostgresURL:   normalizePostgresURL(parsed.PostgresURL),
		ClickHouseURL: parsed.ClickHouseURL,
		RedisURL:      parsed.RedisURL,
		MQTTHost:      parsed.MQTTHost,
		MQTTPort:      parsed.MQTTPort,
	}
	if err := cfg.validateEnv(); err != nil {
		return nil, err
	}
	return cfg, nil
}

func (cfg *Config) validateEnv() error {
	if cfg.MQTTPort < 1 || cfg.MQTTPort > 65535 {
		return apperr.New(apperr.MQTTPortInvalid, "PU_MQTT_PORT must be between 1 and 65535")
	}
	return nil
}

// ApplyRuntime copies the Postgres row onto the fields the pipe reads.
func (cfg *Config) ApplyRuntime(settings RuntimeSettings) error {
	if settings.BufferFlushInterval < 1 {
		return apperr.New(apperr.BufferFlushIntervalInvalid, "pu_datapipe_buffer_flush_interval must be >= 1")
	}
	if settings.BufferMaxSize < 1 {
		return apperr.New(apperr.BufferMaxSizeInvalid, "pu_datapipe_buffer_max_size must be >= 1")
	}
	if settings.ConfigSyncInterval < 1 {
		return apperr.New(apperr.ConfigSyncIntervalInvalid, "pu_datapipe_config_sync_interval must be >= 1")
	}
	if settings.NRecordsCleanupInterval < 1 {
		return apperr.New(apperr.NRecordsCleanupIntervalInvalid, "pu_datapipe_nrecords_cleanup_interval must be >= 1")
	}
	if settings.MQTTKeepAlive < 0 {
		return apperr.New(apperr.MQTTKeepAliveInvalid, "pu_datapipe_mqtt_keepalive must be >= 0")
	}
	if err := logging.Configure(settings.LogMinLevel, settings.LogFormat); err != nil {
		return err
	}

	cfg.BufferFlushInterval = settings.BufferFlushInterval
	cfg.BufferMaxSize = settings.BufferMaxSize
	cfg.ConfigSyncInterval = settings.ConfigSyncInterval
	cfg.MQTTKeepAlive = settings.MQTTKeepAlive
	cfg.NRecordsCleanupInterval = settings.NRecordsCleanupInterval
	cfg.NotificationEnable = settings.NotificationEnable
	cfg.DatapipeEnable = settings.DatapipeEnable
	cfg.LogMinLevel = settings.LogMinLevel
	cfg.LogFormat = settings.LogFormat
	return nil
}

// Runtime returns the settings that came from Postgres.
func (cfg *Config) Runtime() RuntimeSettings {
	return RuntimeSettings{
		BufferFlushInterval:     cfg.BufferFlushInterval,
		BufferMaxSize:           cfg.BufferMaxSize,
		ConfigSyncInterval:      cfg.ConfigSyncInterval,
		MQTTKeepAlive:           cfg.MQTTKeepAlive,
		NRecordsCleanupInterval: cfg.NRecordsCleanupInterval,
		NotificationEnable:      cfg.NotificationEnable,
		DatapipeEnable:          cfg.DatapipeEnable,
		LogMinLevel:             cfg.LogMinLevel,
		LogFormat:               cfg.LogFormat,
	}
}

// WatchRuntime polls Postgres. handle returns true to stop the loop.
func WatchRuntime(
	ctx context.Context,
	every time.Duration,
	load func() (RuntimeSettings, error),
	handle func(RuntimeSettings) bool,
) {
	ticker := time.NewTicker(every)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			next, err := load()
			if err != nil {
				logging.Errorf("Failed to reload instance settings: %v", err)
				continue
			}
			if handle(next) {
				return
			}
		}
	}
}

// InstanceSettingsUUID is the primary key of the only settings row.
func InstanceSettingsUUID() string {
	return instanceSettingsUUID
}

// normalizePostgresURL strips a SQLAlchemy driver suffix.
// postgresql+psycopg2:// becomes postgresql://, which pgx accepts.
func normalizePostgresURL(raw string) string {
	scheme, rest, ok := strings.Cut(raw, "://")
	if !ok {
		return raw
	}
	driver, _, ok := strings.Cut(scheme, "+")
	if !ok {
		return raw
	}
	return driver + "://" + rest
}
