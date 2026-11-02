package phases

import (
	"resolv/pkg/session"
)

func Record(domain string, issue string) error {
	dir := session.Dir(domain, "repo", issue)
	_ = session.AppendAudit(dir, map[string]interface{}{"stage":"record"})
	return nil
}
