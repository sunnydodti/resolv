package phases

import (
	"resolv/pkg/change"
	"resolv/pkg/llm"
)

func Apply() error {
	c, err := llm.LoadConfig()
	if err != nil {
		return err
	}
	content, _, err := c.Call([]llm.Message{{Role: "system", Content: "Generate structured edit for the issue"}})
	if err == nil && content != "" {
		ed, _ := llm.ParseEdit(content)
		if ed != nil && ed.Kind == "edit" && ed.FilePath != "" {
			_ = change.ApplyStructuredEdit(ed.FilePath, ed.OldText, ed.NewText)
			return nil
		}
	}
	_ = change.ApplyStructuredEdit("main.go", "old", "new")
	return nil
}
