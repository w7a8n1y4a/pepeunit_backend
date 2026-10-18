package main

import (
	"context"
	"os"
	"os/signal"
	"syscall"
	"time"

	"data_pipe/internal/config"
	"data_pipe/internal/database"
	"data_pipe/internal/datapipe"
	"data_pipe/internal/logging"
	"data_pipe/internal/mqtt_client"
)

// prSetPdeathsig asks Linux to signal this process when its parent exits.
const prSetPdeathsig = 1

func followParent() {
	_, _, errno := syscall.RawSyscall(
		syscall.SYS_PRCTL, prSetPdeathsig, uintptr(syscall.SIGTERM), 0,
	)
	if errno != 0 || os.Getppid() != 1 {
		return
	}
	logging.Fatalf("Data pipe parent exited")
}

func main() {
	ctx, stop := signal.NotifyContext(
		context.Background(), syscall.SIGINT, syscall.SIGTERM,
	)
	defer stop()
	go func() {
		<-ctx.Done()
		time.Sleep(3 * time.Second)
		os.Exit(0)
	}()
	followParent()

	cfg, err := config.LoadEnv()
	if err != nil {
		logging.Fatalf("Failed to load config: %v", err)
	}

	postgresDB, err := database.NewPostgres(cfg.PostgresURL)
	if err != nil {
		logging.Fatalf("Failed to connect to database: %v", err)
	}
	defer postgresDB.Close()

	runtimeSettings, err := postgresDB.LoadInstanceSettings(ctx)
	if err != nil {
		logging.Fatalf("Failed to load instance settings: %v", err)
	}
	if err := cfg.ApplyRuntime(runtimeSettings); err != nil {
		logging.Fatalf("Invalid instance settings: %v", err)
	}
	if !cfg.DatapipeEnable {
		logging.Infof("Data pipe is disabled")
		return
	}

	logging.Infof(
		"Data pipe config: domain=%s mqtt=%s:%d flush=%ds sync=%ds cleanup=%ds buffer=%d notifications=%t",
		cfg.Domain,
		cfg.MQTTHost,
		cfg.MQTTPort,
		cfg.BufferFlushInterval,
		cfg.ConfigSyncInterval,
		cfg.NRecordsCleanupInterval,
		cfg.BufferMaxSize,
		cfg.NotificationEnable,
	)

	clickhouseDB, err := database.NewClickHouse(cfg.ClickHouseURL)
	if err != nil {
		logging.Fatalf("Failed to connect to ClickHouse: %v", err)
	}
	defer clickhouseDB.Close()

	redisDB, err := database.NewRedis(cfg.RedisURL)
	if err != nil {
		logging.Fatalf("Failed to connect to Redis: %v", err)
	}
	defer redisDB.Close()

	processor := datapipe.NewProcessor(clickhouseDB, postgresDB, cfg)
	configs := datapipe.NewDataPipeConfigs(cfg)
	processor.SetConfigs(configs)
	if err := processor.LoadNodeConfigs(ctx); err != nil {
		logging.Fatalf("Failed to load node configurations: %v", err)
	}

	processor.Start(ctx)

	messageHandler := func(topic string, payload []byte) {
		if err := processor.ProcessMessage(ctx, topic, payload); err != nil {
			return
		}
	}

	mqttClient, err := mqtt_client.New(cfg, messageHandler, postgresDB, func(ctx context.Context) error {
		return processor.LoadNodeConfigs(ctx)
	})
	if err != nil {
		logging.Fatalf("Failed to create MQTT client: %v", err)
	}

	if err := mqttClient.Connect(); err != nil {
		logging.Fatalf("Failed to connect to MQTT broker: %v", err)
	}
	defer mqttClient.Disconnect()

	processor.StartConfigSync(ctx, redisDB, mqttClient)

	reloadCtx, requestReload := context.WithCancel(context.Background())
	defer requestReload()
	started := cfg.Runtime()
	go config.WatchRuntime(ctx, config.RefreshInterval, func() (config.RuntimeSettings, error) {
		return postgresDB.LoadInstanceSettings(ctx)
	}, func(next config.RuntimeSettings) bool {
		if err := logging.Configure(next.LogMinLevel, next.LogFormat); err != nil {
			logging.Errorf("Invalid log settings: %v", err)
		}
		if started.SamePipe(next) {
			return false
		}
		requestReload()
		return true
	})

	select {
	case <-ctx.Done():
		logging.Infof("Shutting down...")
	case <-reloadCtx.Done():
		logging.Infof("Instance settings changed, shutting down data pipe")
	}
}
