package config

import (
	"fmt"
	"os"
)

func LoadGlobalConfig(path string) (*GlobalConfig, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("reading config: %w", err)
	}
	// TODO: use yaml library to decode data into GlobalConfig
	_ = data
	return &GlobalConfig{}, nil
}

func LoadDomainConfig(path string) (*DomainConfig, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("reading domain config: %w", err)
	}
	_ = data
	return &DomainConfig{}, nil
}