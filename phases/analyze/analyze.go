package phases

import (
	"resolv/pkg/context"
	"resolv/pkg/llm"
)

func Analyze() error {
	_, _ = context.GrepFiles([]string{"."}, "func")
	_, _ = context.ParseAST("main.go")
	c, err := llm.LoadConfig()
	if err == nil && c != nil {
		c.Call([]llm.Message{{Role: "system", Content: "Analyze issue payload for root cause"}})
	}
	return nil
}
