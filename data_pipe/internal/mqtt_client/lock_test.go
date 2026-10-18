package mqtt_client

import (
	"syscall"
	"testing"
)

func TestProcLockIDUsesGlibcDevice(t *testing.T) {
	// major 259, minor 3, encoded the way Linux stat stores dev_t.
	stat := &syscall.Stat_t{Dev: 66307, Ino: 49679419}
	got := procLockID(stat)
	want := "103:03:49679419"
	if got != want {
		t.Fatalf("procLockID() = %s, want %s", got, want)
	}
}
