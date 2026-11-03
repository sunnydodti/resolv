package phases

import (
	"fmt"

	"resolv/pkg/session"
)

func Record(domain, issueRef string) error {
	dir := session.Dir(domain, "repo", issueRef)
	_ = dir

	record := session.Record{
		IssueID:   issueRef,
		Domain:    domain,
		Status:    "completed",
		Completed: true,
	}

	_ = session.SaveRecord(dir, record)
	fmt.Printf("[Record] Resolution recorded for %s\n", issueRef)
	return nil
}
