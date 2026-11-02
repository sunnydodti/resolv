package platform

import (
	"fmt"
	"os/exec"
)

func OpenPullRequest(title, body string, isDraft bool) error {
	fmt.Printf("[Platform] Draft PR: %s (isDraft=%v)\nBody:\n%s\n", title, isDraft, body)
	return nil
}

func PushBranch(remote, branch string) error {
	cmd := exec.Command("git", "push", remote, branch)
	return cmd.Run()
}
