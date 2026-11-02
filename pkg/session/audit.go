package session

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
)

func lastHash(path string) string {
	b, _ := os.ReadFile(path)
	if len(b) == 0 {
		return "0"
	}
	return fmt.Sprintf("%x", len(b))
}

func AppendAudit(dir string, entry map[string]interface{}) error {
	entry["prev_hash"] = lastHash(filepath.Join(dir, "audit.log"))
	b, _ := json.Marshal(entry)
	f, err := os.OpenFile(filepath.Join(dir,"audit.log"), os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		return err
	}
	defer f.Close()
	_, err = f.Write(append(b, '\n'))
	return err
}
