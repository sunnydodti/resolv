package change

import (
	"fmt"
	"os"
	"strings"
)

func ApplyStructuredEdit(filePath, oldText, newText string) error {
	data, err := os.ReadFile(filePath)
	if err != nil {
		return fmt.Errorf("read %s: %w", filePath, err)
	}
	s := string(data)
	if !strings.Contains(s, oldText) {
		return fmt.Errorf("oldText not found in %s", filePath)
	}
	s = strings.Replace(s, oldText, newText, 1)
	return os.WriteFile(filePath, []byte(s), 0644)
}
