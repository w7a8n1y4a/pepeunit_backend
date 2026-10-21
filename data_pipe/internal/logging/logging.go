package logging

import (
	"encoding/json"
	"fmt"
	"io"
	"os"
	"runtime"
	"strings"
	"sync"
	"time"

	"data_pipe/internal/apperr"
)

// Levels and formats match the backend instance settings.
const (
	LevelDebug    = "DEBUG"
	LevelInfo     = "INFO"
	LevelWarning  = "WARNING"
	LevelError    = "ERROR"
	LevelCritical = "CRITICAL"

	FormatJSON  = "json"
	FormatPlain = "plain"

	loggerName = "data_pipe"
)

var (
	output io.Writer = os.Stdout
	mu     sync.Mutex
	min    = rank(LevelInfo)
	format = FormatJSON
)

func init() {
	_ = Configure(LevelInfo, FormatJSON)
}

// Configure applies pu_instance_log_min_level and pu_instance_log_format.
// A bad value leaves the previous settings in place.
func Configure(level, logFormat string) error {
	parsedLevel, err := parseLevel(level)
	if err != nil {
		return err
	}
	parsedFormat, err := parseFormat(logFormat)
	if err != nil {
		return err
	}

	mu.Lock()
	min = rank(parsedLevel)
	format = parsedFormat
	mu.Unlock()
	return nil
}

func Debugf(format string, args ...any) {
	write(LevelDebug, fmt.Sprintf(format, args...), 2, false)
}

func Infof(format string, args ...any) {
	write(LevelInfo, fmt.Sprintf(format, args...), 2, false)
}

func Warningf(format string, args ...any) {
	write(LevelWarning, fmt.Sprintf(format, args...), 2, false)
}

func Errorf(format string, args ...any) {
	write(LevelError, fmt.Sprintf(format, args...), 2, false)
}

// Fatalf always prints, then exits. A startup failure stays visible
// even when the configured level would hide it.
func Fatalf(format string, args ...any) {
	write(LevelCritical, fmt.Sprintf(format, args...), 2, true)
	os.Exit(1)
}

func write(level, message string, skip int, force bool) {
	funcName := caller(skip + 1)

	mu.Lock()
	defer mu.Unlock()
	if !force && rank(level) < min {
		return
	}

	now := formatTime(time.Now())
	if format == FormatPlain {
		fmt.Fprintf(output, "%s - %s - %s - %s\n", level, now, loggerName, message)
		return
	}
	fmt.Fprintf(
		output,
		"{\"time\": %s, \"level\": %s, \"logger\": %s, \"message\": %s, \"funcName\": %s}\n",
		quote(now),
		quote(level),
		quote(loggerName),
		quote(message),
		quote(funcName),
	)
}

func caller(skip int) string {
	pc, _, _, ok := runtime.Caller(skip)
	if !ok {
		return "unknown"
	}
	name := runtime.FuncForPC(pc).Name()
	if i := strings.LastIndex(name, "."); i >= 0 {
		name = name[i+1:]
	}
	return name
}

func formatTime(now time.Time) string {
	return now.Format("2006-01-02 15:04:05") + fmt.Sprintf(",%03d", now.Nanosecond()/1e6)
}

func quote(value string) string {
	encoded, err := marshalString(value)
	if err != nil {
		return `""`
	}
	return encoded
}

func marshalString(value string) (string, error) {
	var buf strings.Builder
	encoder := json.NewEncoder(&buf)
	encoder.SetEscapeHTML(false)
	if err := encoder.Encode(value); err != nil {
		return "", err
	}
	return strings.TrimRight(buf.String(), "\n"), nil
}

func parseLevel(raw string) (string, error) {
	switch strings.ToUpper(strings.TrimSpace(raw)) {
	case LevelDebug, LevelInfo, LevelWarning, LevelError, LevelCritical:
		return strings.ToUpper(strings.TrimSpace(raw)), nil
	default:
		return "", apperr.New(
			apperr.LogLevelInvalid,
			"pu_instance_log_min_level must be DEBUG, INFO, WARNING, ERROR or CRITICAL",
		)
	}
}

func parseFormat(raw string) (string, error) {
	switch strings.ToLower(strings.TrimSpace(raw)) {
	case FormatJSON, FormatPlain:
		return strings.ToLower(strings.TrimSpace(raw)), nil
	default:
		return "", apperr.New(apperr.LogFormatInvalid, "pu_instance_log_format must be json or plain")
	}
}

func rank(level string) int {
	switch level {
	case LevelDebug:
		return 10
	case LevelInfo:
		return 20
	case LevelWarning:
		return 30
	case LevelError:
		return 40
	case LevelCritical:
		return 50
	default:
		return 20
	}
}
