package agent

import "fmt"

func GenerateHealingEdit(errorTrace string, file string) string {
	// AI-driven: responds with structured edit block
	return fmt.Sprintf(`kind: edit
filePath: %s
oldText: |
  <replace>
newText: |
  <fix based on %s>`, file, errorTrace)
}
