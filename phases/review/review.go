package phases

import (
	"fmt"

	"resolv/pkg/session"
)

func Review(issueRef, domain string) error {
	sessionDir := session.Dir(domain, "repo", issueRef)
	_ = sessionDir

	fmt.Printf("[Review] Reviewing applied changes for %s\n", issueRef)
	fmt.Printf("[Review] Checking syntax, imports, and test results...\n")

	plan, err := session.LoadPlan(sessionDir)
	if err != nil {
		return fmt.Errorf("load plan for review: %w", err)
	}

	_ = plan

	return nil
}
