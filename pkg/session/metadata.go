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
	return filepath.Join(".resolv", "sessions", fmt.Sprintf("%s_%s_%s", domain, repo, issue))
}

func SaveMetadata(dir string, m Metadata) error {
	b, _ := json.Marshal(m)
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
