package phases

import (
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"resolv/pkg/change"
	"resolv/pkg/context"
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
	meta, _ := session.LoadMetadata(sessionDir)
	workspaceDir := meta.WorkspaceDir
	if workspaceDir == "" || workspaceDir == "." {
		workspaceDir = "."
	}
	prevDir, _ := os.Getwd()
	if workspaceDir != "." && workspaceDir != "" {
		_ = os.Chdir(workspaceDir)
		defer func() { _ = os.Chdir(prevDir) }()
	}
	savedPlan, err := session.LoadPlan(sessionDir)
	if err != nil {
		return fmt.Errorf("load plan: %w", err)
	}

	fileList := context.WorkspaceFileList(workspaceDir, 10)
	editPrompt := fmt.Sprintf("Workspace files: %s. Return exactly one valid JSON array of edit objects: [{ \"file\", \"old\", \"new\" }]. Example: [{\"file\":\"main.go\",\"old\":\"bad\",\"new\":\"good\"}]. file = relative path within workspace repo. old = exact current text, new = exact replacement. If no code changes needed, return [].", fileList)
	msg := []llm.Message{
		{Role: "system", Content: editPrompt},
		{Role: "user", Content: fmt.Sprintf("Issue: %s\nDomain: %s\nSteps:\n%s", issueRef, domain, savedPlan.Steps)},
	}
	resp, _, err := c.Call(msg)
	if err != nil {
		return fmt.Errorf("LLM call failed during apply: %w", err)
	}

	fmt.Printf("[LLM RAW APPLY] %s\n", resp)
	edits := parseEdits(resp)
	// B. Manual verification seed: if zero edits, try manual file
	if len(edits) == 0 {
		manualPath := filepath.Join(sessionDir, "manual_edit.json")
		if b, err := os.ReadFile(manualPath); err == nil {
			var manual []EditSpec
			_ = json.Unmarshal(b, &manual)
			if len(manual) > 0 {
				edits = manual
			}
		}
	}
	if len(edits) == 0 {
		return fmt.Errorf("LLM returned zero edits; apply blocked — output snippet: %s", resp[:min(200,len(resp))])
	}
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
	if len(edits) == 0 {
		return fmt.Errorf("no edits to apply")
	}
	for i, e := range edits {
		if e.File == "" || e.Old == "" || e.New == "" {
			return fmt.Errorf("edit %d missing file/old/new: %+v", i, e)
		}
		if e.New == "" {
			return fmt.Errorf("edit %d has empty new text (use \\n for deletion)", i)
		}
		err := change.ApplyStructuredEdit(e.File, e.Old, e.New)
		if err != nil {
			return fmt.Errorf("edit %d failed for %s: %w", i, e.File, err)
		}
	}
	return nil
}

func parseEdits(resp string) []EditSpec {
	var edits []EditSpec

	// Tight path: valid JSON array of edit objects
	jsonItems := splitJSONArray(resp)
	if len(jsonItems) > 0 {
		for _, item := range jsonItems {
			obj := parseEditObject(item)
			if obj.File != "" {
				edits = append(edits, EditSpec{File: obj.File, Old: obj.Old, New: obj.New})
			}
		}
	}

	// Loose fallback: markdown code block containing JSON
	if len(edits) == 0 && strings.Contains(resp, "```json") {
		startIdx := strings.Index(resp, "```json")
		endIdx := strings.LastIndex(resp, "```")
		if startIdx >= 0 && endIdx > startIdx {
			inner := resp[startIdx+len("```json"):endIdx]
			items := splitJSONArray(inner)
			for _, item := range items {
				obj := parseEditObject(item)
				if obj.File != "" {
					edits = append(edits, EditSpec{File: obj.File, Old: obj.Old, New: obj.New})
				}
			}
		}
	}

	// Extreme fallback: literal `[{...}]` anywhere
	if len(edits) == 0 && strings.Contains(resp, "[{") {
		items := splitJSONArray(resp)
		for _, item := range items {
			obj := parseEditObject(item)
			if obj.File != "" {
				edits = append(edits, EditSpec{File: obj.File, Old: obj.Old, New: obj.New})
			}
		}
	}

	if len(edits) == 0 {
		fmt.Printf("[Apply] LLM output had no structured edits; snippet: %s\n", truncate(resp, 300))
	}
	return edits
}

func truncate(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n] + "..."
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
	oldStart := strings.Index(s, `"old"`)
	if oldStart >= 0 {
		vStart := strings.Index(s[oldStart:], ":") + oldStart
		out.Old = extractJSONString(s[vStart+1 : findClosingBrace(s[vStart+1:])])
	}
	newStart := strings.Index(s, `"new"`)
	if newStart >= 0 {
		vStart := strings.Index(s[newStart:], ":") + newStart
		out.New = extractJSONString(s[vStart+1 : findClosingBrace(s[vStart+1:])])
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
	out, err := cmd2.CombinedOutput()
	if err != nil && strings.Contains(string(out), "nothing to commit") {
		return nil
	}
	if err != nil {
		return fmt.Errorf("commit failed: %w (%s)", err, out)
	}
	return nil
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
