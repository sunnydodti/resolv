package phases

import (
	"fmt"
	"resolv/pkg/change"
	"resolv/pkg/llm"
)

func Apply() error {
	c := llm.NewClient("", "gpt-4o-mini", "")
	content, _, err := c.Call([]llm.Message{{Role: "system", Content: "Generate edit block to fix issue"}})
	if err != nil {
		fmt.Printf("LLM call error: %v\n", err)
		return nil // demo continues
	}
	// Try parse edit from response
	ed, _ := llm.ParseEdit(content)
	if ed != nil && ed.Kind == "edit" && ed.FilePath != "" {
		_ = change.ApplyStructuredEdit(ed.FilePath, ed.OldText, ed.NewText)
	} else {
		_ = change.ApplyStructuredEdit("main.go", "old", content)
	}
	return nil
}
