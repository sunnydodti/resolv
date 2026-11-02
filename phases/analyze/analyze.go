package phases

import (
	"resolv/pkg/context"
	"resolv/pkg/llm"
)

func Analyze() error {
	// Call context agent tools
	_, _ = context.GrepFiles([]string{"."}, "func")
	_, _ = context.ParseAST("main.go")
	// Call LLM for issue intent
	c := &llm.Client{}
	_, _, _ = c.Call([]llm.Message{{Role: "system", Content: "Analyze issue"}})
	return nil
}
