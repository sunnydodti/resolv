package phases

import (
	"fmt"
	"strings"

	"resolv/pkg/llm"
	"resolv/pkg/session"
)

func Plan(issueRef, domain string) error {
	c, err := llm.LoadConfig()
	if err != nil || c == nil {
		return fmt.Errorf("LLM config not available for planning")
	}

	msg := []llm.Message{
		{Role: "system", Content: "Generate a resolution plan for the GitHub issue. Return JSON: {steps: [\"step1\",\"step2\"], suggested_fix: \"code fix description\", affected_files: [\"file1.go\", \"file2.go\"]}"},
		{Role: "user", Content: fmt.Sprintf("Issue: %s\nDomain: %s", issueRef, domain)},
	}
	resp, _, err := c.Call(msg)
	fmt.Printf("[LLM RAW PLAN] %s\n", resp)
	if err != nil {
		return fmt.Errorf("LLM call failed during plan: %w", err)
	}

	result := parsePlan(resp)

	sessionDir := session.Dir(domain, "repo", issueRef)
	planData := session.Plan{
		Steps:        result.Steps,
		Boundaries:   []string{},
	}
	_ = session.SavePlan(sessionDir, planData)

	fmt.Printf("[Plan] Generated %d resolution steps\n", len(result.Steps))
	return nil
}

type PlanResult struct {
	Steps      []string
	SuggestFix string
	AffectedFC []string
}

func parsePlan(resp string) PlanResult {
	var res PlanResult
	idx := strings.Index(resp, "\"steps\":")
	if idx >= 0 {
		rest := resp[idx+len("\"steps\":"):]
		if nl := strings.IndexAny(rest, "\"],"); nl > 0 {
			arrVal := rest[:nl]
			if strings.HasPrefix(strings.TrimSpace(arrVal), "[") {
				out := splitLines(arrVal[1 : len(arrVal)-1])
				for _, line := range out {
					line = strings.TrimSpace(line)
					if line != "" {
						res.Steps = append(res.Steps, line)
					}
				}
			} else {
				for _, line := range splitLines(arrVal) {
					line = strings.TrimSpace(line)
					if line != "" {
						res.Steps = append(res.Steps, line)
					}
				}
			}
		}
	}
	if idx := strings.Index(resp, "\"suggested_fix\":"); idx >= 0 {
		rest := resp[idx+len("\"suggested_fix\":"):]
		if nl := strings.IndexAny(rest, "\n]}"); nl > 0 {
			res.SuggestFix = strings.TrimSpace(rest[:nl])
		}
	}
	if idx := strings.Index(resp, "\"affected_files\":"); idx >= 0 {
		rest := resp[idx+len("\"affected_files\":"):]
		if arrStart := strings.Index(rest, "["); arrStart >= 0 {
			rest2 := rest[arrStart:]
			lines := splitLines(rest2)
			for _, line := range lines {
				line = strings.TrimSpace(line)
				if line != "" {
					res.AffectedFC = append(res.AffectedFC, line)
				}
			}
		}
	}
	return res
}

func splitLines(s string) []string {
	var out []string
	for _, line := range strings.Split(s, ",") {
		line = strings.TrimSpace(line)
		if line != "" {
			out = append(out, line)
		}
	}
	return out
}
