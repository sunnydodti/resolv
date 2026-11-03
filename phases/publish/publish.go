package phases

import (
	"fmt"

	"resolv/pkg/platform"
)

func Publish(issueRef, domain string) error {
	title := fmt.Sprintf("Resolv fix (%s)", domain)
	body := fmt.Sprintf("Auto PR for %s\n\nPipeline completed all stages.", issueRef)

	res, err := platform.OpenPullRequest(title, body, true)
	if err != nil {
		return fmt.Errorf("open PR failed: %w", err)
	}

	fmt.Printf("[Publish] PR created successfully: %v\n", res)
	return nil
}
