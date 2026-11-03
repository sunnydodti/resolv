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

func LoadPlan(dir string) (Plan, error) {
	var p Plan
	b, err := os.ReadFile(filepath.Join(dir, "plan.json"))
	if err != nil {
		return p, err
	}
	err = json.Unmarshal(b, &p)
	return p, err
}
