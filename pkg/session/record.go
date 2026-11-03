package session

import (
	"encoding/json"
	"os"
	"path/filepath"
)

type Record struct {
	IssueID   string `json:"issue_id"`
	Domain    string `json:"domain"`
	Status    string `json:"status"`
	Completed bool   `json:"completed"`
}

func SaveRecord(dir string, r Record) error {
	b, _ := json.Marshal(r)
	return os.WriteFile(filepath.Join(dir,"record.json"), b, 0644)
}

func LoadRecord(dir string) (Record, error) {
	var r Record
	b, err := os.ReadFile(filepath.Join(dir,"record.json"))
	if err != nil {
		return r, err
	}
	err = json.Unmarshal(b, &r)
	return r, err
}
