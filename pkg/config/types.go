package config

import "time"

type GlobalConfig struct {
	Version   string       `yaml:"version" json:"version"`
	Model     ModelConfig  `yaml:"model" json:"model"`
	Execution ExecutionConfig `yaml:"execution" json:"execution"`
	Telemetry TelemetryConfig `yaml:"telemetry" json:"telemetry"`
}

type ModelConfig struct {
	Provider        string  `yaml:"provider" json:"provider"`
	ModelName       string  `yaml:"model_name" json:"model_name"`
	Endpoint        string  `yaml:"endpoint,omitempty" json:"endpoint,omitempty"`
	Timeout         int     `yaml:"timeout" json:"timeout"`
	MaxTokens       int     `yaml:"max_tokens" json:"max_tokens"`
	Temperature     float32 `yaml:"temperature" json:"temperature"`
	CredentialKey   string  `yaml:"credential_key" json:"credential_key"`
}

type ExecutionConfig struct {
	MaxIterations      int      `yaml:"max_iterations" json:"max_iterations"`
	Interactive        bool     `yaml:"interactive" json:"interactive"`
	AllowedDirectories []string `yaml:"allowed_directories" json:"allowed_directories"`
	DenyPatterns       []string `yaml:"deny_patterns" json:"deny_patterns"`
	ExecutionTimeout   time.Duration `yaml:"execution_timeout" json:"execution_timeout"`
	AutoCommit         bool     `yaml:"auto_commit" json:"auto_commit"`
}

type TelemetryConfig struct {
	Enabled      bool   `yaml:"enabled" json:"enabled"`
	ExporterHost string   `yaml:"exporter_host,omitempty" json:"exporter_host,omitempty"`
	SampleRate   float64  `yaml:"sample_rate" json:"sample_rate"`
	AuditLogPath string   `yaml:"audit_log_path" json:"audit_log_path"`
}