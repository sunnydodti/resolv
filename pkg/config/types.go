package config

type GlobalConfig struct {
	Version   string `json:"version"`
	Model     ModelConfig `json:"model"`
	Execution ExecutionConfig `json:"execution"`
	Telemetry TelemetryConfig `json:"telemetry"`
	Platforms []string      `json:"platforms,omitempty"`
	Tokens    map[string][]string `json:"tokens,omitempty"`
}

type ModelConfig struct {
	Provider        string `json:"provider"`
	ModelName       string `json:"model_name"`
	Endpoint        string `json:"endpoint,omitempty"`
	Timeout         int    `json:"timeout"`
	MaxTokens       int    `json:"max_tokens"`
	Temperature     float32 `json:"temperature"`
	CredentialKey   string `json:"credential_key"`
}

type ExecutionConfig struct {
	MaxIterations      int `json:"max_iterations"`
	Interactive        bool `json:"interactive"`
	AllowedDirectories []string `json:"allowed_directories"`
	DenyPatterns       []string `json:"deny_patterns"`
	ExecutionTimeout   int `json:"execution_timeout"`
	AutoCommit         bool `json:"auto_commit"`
}

type TelemetryConfig struct {
	Enabled      bool     `json:"enabled"`
	ExporterHost string   `json:"exporter_host,omitempty"`
	SampleRate   float64  `json:"sample_rate"`
	AuditLogPath string   `json:"audit_log_path"`
}

// Repo represents a git repository reference.
type Repo struct {
	Source         string `json:"source"`
	BasePath       string `json:"base_path"`
	RepoPath       string `json:"repo_path"`
	CredentialKey  string `json:"credential_key,omitempty"`
}

// DomainEntry holds the settings for a single domain.
type DomainEntry struct {
	Repos  map[string][]Repo   `json:"repos"`   // key: repo type (primary/reference/other)
	Tokens map[string][]string `json:"tokens,omitempty"`
}

// DomainConfig holds all domains in domain.yml.
type DomainConfig struct {
	Domains map[string]DomainEntry `json:"domains"`
}