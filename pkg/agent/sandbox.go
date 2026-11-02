package agent

import (
	"context"
	"fmt"
	"os/exec"
	"time"
)

func RunSandboxCommand(cmdStr string, timeoutSec int) (string, error) {
	ctx, cancel := context.WithTimeout(context.Background(), time.Duration(timeoutSec)*time.Second)
	defer cancel()
	cmd := exec.CommandContext(ctx, "sh", "-c", cmdStr)
	out, err := cmd.CombinedOutput()
	if ctx.Err() == context.DeadlineExceeded {
		return "", fmt.Errorf("timeout after %ds: %w", timeoutSec, err)
	}
	return string(out), err
}
