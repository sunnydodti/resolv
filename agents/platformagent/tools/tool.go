package tools

import "resolv/pkg/platform"

func OpenPullRequest(title, body string, isDraft bool) error { return platform.OpenPullRequest(title, body, isDraft) }
func GeneratePRSummary(commits, tests string) string { return "summary" }
func GenerateIssueGapsReport(failureTraces, attemptedFixes string) string { return platform.GenerateIssueGapsReport(failureTraces, attemptedFixes) }
