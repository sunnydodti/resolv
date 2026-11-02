package platform

import "fmt"

func GenerateIssueGapsReport(failureTraces, attemptedFixes string) string {
	return fmt.Sprintf("## Unresolved / Issue Gaps\n- Errors: %s\n- Fixes tried: %s", failureTraces, attemptedFixes)
}
