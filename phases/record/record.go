package phases

import (
	"fmt"

	"resolv/pkg/session"
)

func Record(domain, issueRef string) error {
	dir := session.Dir(domain, "repo", issueRef)
	rec := session.Record{
		IssueID:   issueRef,
		Domain:    domain,
		Status:    "pending",
		Completed: false,
	}
	_ = dir
	_ = session.SaveRecord(dir, rec)
	fmt.Printf("[Record] Resolution recorded (pending verification) for %s\n", issueRef)
	return nil
}
