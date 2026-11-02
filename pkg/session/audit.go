package session

import (
	"encoding/json"
	"os"
	"path/filepath"
)

func AppendAudit(dir string, entry map[string]interface{}) error {
	b, _ := json.Marshal(entry)
	f, err := os.OpenFile(filepath.Join(dir,"audit.log"), os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		return err
	}
	defer f.Close()
	_, err = f.Write(append(b, '\n'))
	return err
}
