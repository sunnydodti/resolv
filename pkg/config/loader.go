package config

import (
	"fmt"
	"os"
	"path/filepath"
)

// ConfigDir returns the directory where Resolv stores its configuration.
// It respects the RESOLV_CONFIG_DIR environment variable if set.
// On all platforms the default is $HOME/.resolv (or %HOME% on Windows).
func ConfigDir() string {
	if d := os.Getenv("RESOLV_CONFIG_DIR"); d != "" {
		return d
	}
	home, err := os.UserHomeDir()
	if err != nil {
		return ".resolv" // fallback to CWD hidden dir
	}
	return filepath.Join(home, ".resolv")
}

// LoadGlobalConfig reads the global configuration from the config directory.
func LoadGlobalConfig() (*GlobalConfig, error) {
	path := filepath.Join(ConfigDir(), "resolv.yml")
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("reading config: %w", err)
	}
	_ = data
	return &GlobalConfig{}, nil
}

// LoadDomainConfig reads the domain configuration from the config directory.
func LoadDomainConfig() (*DomainConfig, error) {
	path := filepath.Join(ConfigDir(), "domain.yml")
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("reading domain config: %w", err)
	}
	_ = data
	return &DomainConfig{}, nil
}