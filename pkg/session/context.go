package session

import (
	"encoding/json"
	"os"
	"path/filepath"
)

type Context struct {
	GrepHits []string `json:"grep_hits"`
	Symbols  []string `json:"symbols"`
}

func SaveContext(dir string, c Context) error {
	b, _ := json.Marshal(c)
	return os.WriteFile(filepath.Join(dir, "context.json"), b, 0644)
}
