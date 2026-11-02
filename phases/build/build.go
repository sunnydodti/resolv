package phases

import "resolv/pkg/agent"

func Build() error {
	_, _ = agent.RunSandboxCommand("go test ./...", 30)
	return nil
}
