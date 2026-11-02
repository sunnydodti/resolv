package change

import (
	"fmt"
	"os/exec"
)

func CreateWorktree(repoPath, branch string) error {
	cmd := exec.Command("git", "worktree", "add", "-b", branch, branch)
	cmd.Dir = repoPath
	out, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("worktree create %s: %w (%s)", branch, err, out)
	}
	return nil
}
