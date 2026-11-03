package phases

import (
	"fmt"
	"os/exec"
	"strings"

	"resolv/pkg/context"
	"resolv/pkg/llm"
	"resolv/pkg/session"
)

func Analyze(issueRef, domain string) error {
	_ = session.Dir(domain, "repo", issueRef)

	c, err := llm.LoadConfig()
	if err != nil || c == nil {
		return fmt.Errorf("LLM config not available for analysis")
	}

	issueText := loadIssuePayload(issueRef)

	msg := []llm.Message{
		{Role: "system", Content: "Analyze the GitHub issue payload for root cause."},
		{Role: "user", Content: issueText},
	}
	resp, _, err := c.Call(msg)
	if err != nil {
		return fmt.Errorf("LLM call failed during analyze: %w", err)
	}

	result := parseAnalysis(resp)

	context.GrepFiles([]string{"."}, "func")
	_, err = context.ParseAST("main.go")
	_ = err

	_ = session.Dir(domain, "repo", issueRef)

	fmt.Printf("[Analyze] Root cause: %s | Severity: %s\n", result.RootCause, result.Severity)
	return nil
}

type AnalysisResult struct {
	RootCause  string
	AffectedFC []string
	Severity   string
	PlanSteps  string
}

func parseAnalysis(resp string) AnalysisResult {
	rootCause := "Unknown"
	severity := "medium"
	if idx := strings.Index(resp, "Root cause:"); idx >= 0 {
		rest := resp[idx+len("Root cause:"):]
		if nl := strings.Index(rest, "\n"); nl > 0 {
			rootCause = rest[:nl]
		} else {
			rootCause = rest
		}
	}
	if idx := strings.Index(resp, "Severity:"); idx >= 0 {
		rest := resp[idx+len("Severity:"):]
		if nl := strings.IndexAny(rest, ",.\n"); nl > 0 {
			severity = strings.TrimSpace(rest[:nl])
		} else {
			severity = strings.TrimSpace(rest)
		}
	}
	return AnalysisResult{RootCause: rootCause, Severity: severity, AffectedFC: []string{}, PlanSteps: resp}
}

func loadIssuePayload(issueRef string) string {
	parts := strings.SplitN(issueRef, "/", 2)
	if len(parts) < 2 {
		return "Issue reference not parseable"
	}
	repo := parts[0]
	branch := parts[1]
	cmd := exec.Command("curl", "-s", "-L", fmt.Sprintf("https://api.github.com/repos/%s/issues/%s", repo, branch))
	out, _ := cmd.Output()
	if len(out) > 10 {
		return string(out)
	}
	return issueRef
}
