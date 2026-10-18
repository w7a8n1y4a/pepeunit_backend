package cleanup

import (
	"context"
	"time"

	"data_pipe/internal/config"
	"data_pipe/internal/database"
	"data_pipe/internal/logging"
)

// NRecordsCleanupService handles periodic cleanup of NRecords entries
type NRecordsCleanupService struct {
	clickhouseDB *database.ClickHouseDB
	cfg          *config.Config
	stopCh       chan struct{}
}

// NewNRecordsCleanupService creates a new NRecords cleanup service
func NewNRecordsCleanupService(clickhouseDB *database.ClickHouseDB, cfg *config.Config) *NRecordsCleanupService {
	return &NRecordsCleanupService{
		clickhouseDB: clickhouseDB,
		cfg:          cfg,
		stopCh:       make(chan struct{}),
	}
}

// Start begins the periodic cleanup process
func (s *NRecordsCleanupService) Start(ctx context.Context) {
	go func() {
		ticker := time.NewTicker(time.Duration(s.cfg.NRecordsCleanupInterval) * time.Second)
		defer ticker.Stop()

		for {
			select {
			case <-ticker.C:
				if err := s.cleanup(ctx); err != nil {
					logging.Errorf("Failed to cleanup NRecords: %v", err)
				}
			case <-s.stopCh:
				return
			case <-ctx.Done():
				return
			}
		}
	}()
}

// Stop stops the cleanup service
func (s *NRecordsCleanupService) Stop() {
	close(s.stopCh)
}

// cleanup performs the actual cleanup operation
func (s *NRecordsCleanupService) cleanup(ctx context.Context) error {
	if err := s.clickhouseDB.CleanupNLastEntries(ctx); err != nil {
		return err
	}
	logging.Infof("Success NRecords cleanup")
	return nil
}
