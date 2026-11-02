package change

import (
	"bytes"
	"fmt"
	"os/exec"
)

func ApplyGitDiffFallback(repoPath string, diff []byte) error {
	cmd := exec.Command("git", "apply")
	cmd.Dir = repoPath
	cmd.Stdin = bytes.NewReader(diff)
	out, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("git apply: %w (%s)", err, out)
	}
	return nil
}
