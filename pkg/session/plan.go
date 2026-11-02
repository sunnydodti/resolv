package session

import (
	"encoding/json"
	"os"
	"path/filepath"
)

type Plan struct {
	Steps      []string `json:"steps"`
	Boundaries []string `json:"boundaries"`
}

func SavePlan(dir string, p Plan) error {
	b, _ := json.Marshal(p)
	return os.WriteFile(filepath.Join(dir,"plan.json"), b, 0644)
}
