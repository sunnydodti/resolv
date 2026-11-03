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

	issueFiles := context.WorkspaceFileList(".", 15)
	msg := []llm.Message{
		{Role: "system", Content: fmt.Sprintf("Analyze the GitHub issue for root cause or enhancement scope. Workspace source files available: %s. State if this is a bug or feature request.", issueFiles)},
		{Role: "user", Content: fmt.Sprintf("Issue: %s\nDomain: %s\n%s", issueText, domain, issueFiles)},
	}
	resp, _, err := c.Call(msg)
	fmt.Printf("[LLM RAW ANALYZE] %s\n", resp)
	if err != nil {
		return fmt.Errorf("LLM call failed during analyze: %w", err)
	}

	result := parseAnalysis(resp)

	context.GrepFiles([]string{"."}, "func")
	_, err = context.ParseAST("main.go")
	_ = err

	_ = session.Dir(domain, "repo", issueRef)

	fmt.Printf("[Analyze] Root cause / enhancement scope: %s | Severity: %s (bug=%v)\n", result.RootCause, result.Severity, result.RootCause != "Not found in LLM output" && result.Severity != "unknown")
	return nil
}

type AnalysisResult struct {
	RootCause  string
	AffectedFC []string
	Severity   string
	PlanSteps  string
}

func parseAnalysis(resp string) AnalysisResult {
	rootCause := "Not found in LLM output"
	severity := "unknown"
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
	// Expected: https://github.com/sunnydodti/resolv/issues/1
	if strings.HasPrefix(issueRef, "https://github.com/") {
		parts := strings.Split(issueRef, "/")
		if len(parts) >= 5 && parts[len(parts)-2] == "issues" {
			repo := parts[3] + "/" + parts[4]
			issueNum := parts[len(parts)-1]
			cmd := exec.Command("curl", "-s", "-L", fmt.Sprintf("https://api.github.com/repos/%s/issues/%s", repo, issueNum))
			out, _ := cmd.Output()
			if len(out) > 10 {
				return string(out)
			}
		}
	}
	return issueRef
}
