package phases

import (
	"resolv/pkg/config"
	"resolv/pkg/llm"
)

func Plan() error {
	_ = config.Repo{}
	c := &llm.Client{}
	_, _, _ = c.Call([]llm.Message{{Role: "system", Content: "Generate resolution plan"}})
	return nil
}
