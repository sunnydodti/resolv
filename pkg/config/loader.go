package config

import (
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"

	"gopkg.in/yaml.v3"
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

// LoadGlobalConfig reads and decodes the global configuration from the config directory.
func LoadGlobalConfig() (*GlobalConfig, error) {
	path := filepath.Join(ConfigDir(), "resolv.yml")
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("reading global config: %w", err)
	}
	var cfg GlobalConfig
	if err := yaml.Unmarshal(data, &cfg); err != nil {
		return nil, fmt.Errorf("decoding global config: %w", err)
	}
	return &cfg, nil
}

// SaveGlobalConfig writes the global configuration atomically.
func SaveGlobalConfig(cfg *GlobalConfig) error {
	dir := ConfigDir()
	if err := os.MkdirAll(dir, 0750); err != nil {
		return err
	}
	data, err := yaml.Marshal(cfg)
	if err != nil {
		return err
	}
	tmp := filepath.Join(dir, "resolv.yml.tmp")
	if err := os.WriteFile(tmp, data, 0644); err != nil {
		return err
	}
	return os.Rename(tmp, filepath.Join(dir, "resolv.yml"))
}

// LoadDomainConfig reads and decodes the domain configuration from the config directory.
func LoadDomainConfig() (*DomainConfig, error) {
	path := filepath.Join(ConfigDir(), "domain.yml")
	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return &DomainConfig{}, nil
		}
		return nil, fmt.Errorf("reading domain config: %w", err)
	}
	var cfg DomainConfig
	if err := yaml.Unmarshal(data, &cfg); err != nil {
		return nil, fmt.Errorf("decoding domain config: %w", err)
	}
	return &cfg, nil
}

// SaveDomainConfig writes the domain configuration atomically.
func SaveDomainConfig(cfg *DomainConfig) error {
	dir := ConfigDir()
	if err := os.MkdirAll(dir, 0750); err != nil {
		return err
	}
	data, err := yaml.Marshal(cfg)
	if err != nil {
		return err
	}
	tmp := filepath.Join(dir, "domain.yml.tmp")
	if err := os.WriteFile(tmp, data, 0644); err != nil {
		return err
	}
	return os.Rename(tmp, filepath.Join(dir, "domain.yml"))
}

// LoadCredentials reads the credentials JSON file if present.
func LoadCredentials() (map[string]string, error) {
	path := filepath.Join(ConfigDir(), "credentials.json")
	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return map[string]string{}, nil
		}
		return nil, fmt.Errorf("reading credentials: %w", err)
	}
	var creds map[string]string
	if err := json.Unmarshal(data, &creds); err != nil {
		return nil, fmt.Errorf("decoding credentials: %w", err)
	}
	return creds, nil
}

// SaveCredentials writes credentials JSON atomically with restricted perms.
func SaveCredentials(creds map[string]string) error {
	dir := ConfigDir()
	if err := os.MkdirAll(dir, 0700); err != nil {
		return err
	}
	data, err := json.MarshalIndent(creds, "", "  ")
	if err != nil {
		return err
	}
	tmp := filepath.Join(dir, "credentials.json.tmp")
	if err := os.WriteFile(tmp, data, 0600); err != nil {
		return err
	}
	return os.Rename(tmp, filepath.Join(dir, "credentials.json"))
}

// LoadDomainEntry reads a single domain config from /domains/<name>/config.yml.
func LoadDomainEntry(name string) (*DomainEntry, error) {
	dir := filepath.Join(ConfigDir(), "domains", name)
	f := filepath.Join(dir, "config.yml")
	if _, err := os.Stat(f); os.IsNotExist(err) {
		return &DomainEntry{Repos: map[string][]Repo{}}, nil
	}
	data, err := os.ReadFile(f)
	if err != nil {
		return nil, fmt.Errorf("reading domain %s: %w", name, err)
	}
	var entry DomainEntry
	if err := yaml.Unmarshal(data, &entry); err != nil {
		return nil, fmt.Errorf("decoding domain %s: %w", name, err)
	}
	return &entry, nil
}

// SaveDomainEntry writes a single domain config atomically.
func SaveDomainEntry(name string, entry *DomainEntry) error {
	dir := filepath.Join(ConfigDir(), "domains", name)
	if err := os.MkdirAll(dir, 0750); err != nil {
		return err
	}
	data, err := yaml.Marshal(entry)
	if err != nil {
		return err
	}
	tmp := filepath.Join(dir, "config.yml.tmp")
	if err := os.WriteFile(tmp, data, 0644); err != nil {
		return err
	}
	return os.Rename(tmp, filepath.Join(dir, "config.yml"))
}

// ensure io import used
var _ = io.EOF