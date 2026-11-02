package session

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
)

type Metadata struct {
	IssueID        string `json:"issue_id"`
	Domain         string `json:"domain"`
	RepoPath       string `json:"repo_path"`
	CurrentStage   int    `json:"current_stage"`
	CreatedAt      string `json:"created_at"`
}

func Dir(domain, repo, issue string) string {
	configDir := ".resolv"
	if _, err := os.Stat(".resolv/resolv.yml"); err != nil {
		if home, err := os.UserHomeDir(); err == nil {
			configDir = filepath.Join(home, ".resolv")
		}
	}
	return filepath.Join(configDir, "sessions", fmt.Sprintf("%s_%s_%s", domain, repo, issue))
}

func SaveMetadata(dir string, m Metadata) error {
	os.MkdirAll(dir, 0750)
	b, err := json.Marshal(m)
	if err != nil {
		return err
	}
	return os.WriteFile(filepath.Join(dir, "metadata.json"), b, 0644)
}

func LoadMetadata(dir string) (Metadata, error) {
	var m Metadata
	b, err := os.ReadFile(filepath.Join(dir, "metadata.json"))
	if err != nil {
		return m, err
	}
	err = json.Unmarshal(b, &m)
	return m, err
}
