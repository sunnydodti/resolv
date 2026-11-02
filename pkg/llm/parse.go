package llm

import (
	"encoding/json"
	"fmt"
	"regexp"
	"strings"
)

type EditBlock struct {
	Kind     string `json:"kind"`
	FilePath string `json:"file_path"`
	OldText  string `json:"oldText"`
	NewText  string `json:"newText"`
}

func ParseEdit(content string) (*EditBlock, error) {
	// Try structured JSON first
	if idx := strings.Index(content, "{"); idx != -1 {
		// Simple extraction of JSON block between braces
		start := idx
		brace := 1
		end := start + 1
		for end < len(content) && brace > 0 {
			c := content[end]
			if c == '{' {
				brace++
			} else if c == '}' {
				brace--
			}
			end++
		}
		if brace == 0 {
			var e EditBlock
			if err := json.Unmarshal([]byte(content[start:end]), &e); err == nil && e.Kind == "edit" {
				return &e, nil
			}
		}
	}

	// Fallback
	re := regexp.MustCompile(`kind:\s*"?edit"?`)
	if !re.MatchString(content) {
		return nil, fmt.Errorf("no edit block found")
	}
	// Derive from context if structured parse fails — for v1, require JSON
	return nil, fmt.Errorf("structured edit parse failed; expected JSON format")
}
