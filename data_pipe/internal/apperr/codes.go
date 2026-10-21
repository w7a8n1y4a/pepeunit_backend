// Package apperr holds numeric codes for data pipe errors a person can act on.
// The numbers share the Python catalog: domain 316 is DataPipe, local 500–699
// is reserved for this process. Infrastructure failures stay uncoded.
package apperr

import "fmt"

// Code is DDDLLL, the same shape as Python ErrorCode.
type Code int

const (
	InvalidTopic                   Code = 316500
	InvalidNodeUUID                Code = 316510
	PolicyConfigMissing            Code = 316520
	AggregationFunctionsMissing    Code = 316530
	TimeWindowSizeMissing          Code = 316540
	StateNotFloat                  Code = 316550
	InvalidPolicyConfiguration     Code = 316560
	NoBuffer                       Code = 316570
	UnknownPolicyType              Code = 316580
	NRecordsCountMissing           Code = 316590
	FiltersConfigMissing           Code = 316600
	AlertUserUUID                  Code = 316610
	AlertPayload                   Code = 316620
	LogFormatInvalid               Code = 316630
	LogLevelInvalid                Code = 316640
	MQTTPortInvalid                Code = 316650
	BufferFlushIntervalInvalid     Code = 316660
	BufferMaxSizeInvalid           Code = 316670
	ConfigSyncIntervalInvalid      Code = 316680
	NRecordsCleanupIntervalInvalid Code = 316690
	MQTTKeepAliveInvalid           Code = 316700
)

// Error is a final data pipe failure with a stable code.
type Error struct {
	Code Code
	text string
	err  error
}

// New builds an error whose text is shown in logs next to the code.
func New(code Code, format string, args ...any) error {
	return &Error{Code: code, text: fmt.Sprintf(format, args...)}
}

// Wrap attaches a cause without dropping the stable code.
func Wrap(code Code, err error, format string, args ...any) error {
	return &Error{Code: code, text: fmt.Sprintf(format, args...), err: err}
}

func (e *Error) Error() string {
	// PUER is only the log form. The code value stays the bare number.
	if e.err != nil {
		return fmt.Sprintf("PUER%d: %s: %v", e.Code, e.text, e.err)
	}
	return fmt.Sprintf("PUER%d: %s", e.Code, e.text)
}

func (e *Error) Unwrap() error {
	return e.err
}
