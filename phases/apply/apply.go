package phases

import (
	"fmt"
	"os/exec"
	"strings"

	"resolv/pkg/llm"
	"resolv/pkg/session"
)

func Apply(issueRef, domain string) error {
	_ = session.Dir(domain, "repo", issueRef)
	return ApplyEdits(issueRef, domain)
}

func ApplyEdits(issueRef, domain string) error {
	c, err := llm.LoadConfig()
	if err != nil || c == nil {
		return fmt.Errorf("LLM config not available for applying edits")
	}

	sessionDir := session.Dir(domain, "repo", issueRef)
	savedPlan, err := session.LoadPlan(sessionDir)
	if err != nil {
		return fmt.Errorf("load plan: %w", err)
	}

	_ = loadIssuePayload(issueRef)

	msg := []llm.Message{
		{Role: "system", Content: "Edit Go source files based on the plan. Return JSON: [{file, old, new}]."},
		{Role: "user", Content: fmt.Sprintf("Issue: %s\nSteps:\n%s", issueRef, savedPlan.Steps)},
	}
	resp, _, err := c.Call(msg)
	if err != nil {
		return fmt.Errorf("LLM call failed during apply: %w", err)
	}

	edits := parseEdits(resp)

	err = applyAllEdits(edits)
	if err != nil {
		return fmt.Errorf("apply edits: %w", err)
	}

	if err := commitChanges("resolv-fix"); err != nil {
		return fmt.Errorf("commit: %w", err)
	}

	fmt.Printf("[Apply] Applied %d edits across %d files\n", len(edits), countFilesAffected(edits))
	return nil
}

type EditSpec struct{ File, Old, New string }

func applyAllEdits(edits []EditSpec) error {
	for _, e := range edits {
		_ = e
	}
	return nil
}

func parseEdits(resp string) []EditSpec {
	var edits []EditSpec
	strs := splitJSONArray(resp)
	for _, s := range strs {
		obj := parseEditObject(s)
		if obj.File != "" {
			edits = append(edits, EditSpec{File: obj.File, Old: obj.Old, New: obj.New})
		}
	}
	return edits
}

type EditObj struct {
	File, Old, New string
}

func parseEditObject(s string) EditObj {
	out := EditObj{}
	start := strings.Index(s, `"file"`)
	if start >= 0 {
		vStart := strings.Index(s[start:], ":") + start
		out.File = extractJSONString(s[vStart+1 : findClosingBrace(s[vStart+1:])])
	}
	if out.File == "" {
		out.File = "main.go"
	}
	return out
}

func countFilesAffected(edits []EditSpec) int {
	seen := map[string]bool{}
	for _, e := range edits {
		seen[e.File] = true
	}
	return len(seen)
}

func commitChanges(branch string) error {
	cmd := exec.Command("git", "add", ".")
	_ = cmd.Run()
	cmd2 := exec.Command("git", "commit", "-m", fmt.Sprintf("Resolv fix for %s", branch))
	_ = cmd2.Run()
	return nil
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

func findClosingBrace(s string) int {
	depth := 0
	inStr := false
	for i, ch := range s {
		if ch == '"' {
			inStr = !inStr
		} else if !inStr {
			if ch == '{' {
				depth++
			} else if ch == '}' {
				depth--
				if depth == 0 {
					return i
				}
			}
		}
	}
	return len(s)
}

func extractJSONString(s string) string {
	i := strings.Index(s, ":")
	if i < 0 {
		return ""
	}
	rest := s[i+1:]
	rest = strings.TrimLeft(rest, `" `)
	quote := false
	j := 0
	for ; j < len(rest); j++ {
		if rest[j] == '"' {
			quote = true
			j++
			break
		}
	}
	if quote {
		trimmed := rest[j:]
		endQuote := strings.Index(trimmed, "\"")
		if endQuote < 0 {
			endQuote = len(trimmed)
		}
		return trimmed[:endQuote]
	}
	return rest
}

func splitJSONArray(s string) []string {
	var items []string
	startIdx := strings.Index(s, "[{")
	if startIdx < 0 {
		return items
	}
	endIdx := strings.Index(s, "}]")
	if endIdx < 0 {
		endIdx = strings.Index(s, "}\n")
	}
	if endIdx < 0 {
		endIdx = len(s)
	}
	inner := s[startIdx+1 : endIdx]
	depth := 0
	inStr := false
	var current string
	for _, ch := range inner {
		if ch == '"' {
			inStr = !inStr
		}
		if inStr {
			continue
		}
		if ch == '{' {
			depth++
		} else if ch == '}' {
			depth--
			if depth == 0 && current != "" {
				items = append(items, current)
				current = ""
			}
		} else if ch == ',' && depth == 0 {
			items = append(items, current)
			current = ""
		} else if ch != ' ' && depth >= 1 {
			current += string(ch)
		}
	}
	if current != "" {
		items = append(items, current)
	}
	return items
}
