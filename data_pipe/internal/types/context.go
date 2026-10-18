package types

// ContextKey is a custom type for context keys
type ContextKey string

const (
	PolicyKey  ContextKey = "policy"
	FiltersKey ContextKey = "filters"
)
