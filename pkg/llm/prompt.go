package llm

import "fmt"

const (
	AnalyzePrompt = `You are analyzing a git issue. Provide structured reasoning.
Issue: %s
Context: %s
Respond with root-cause category and needed files.`

	PlanPrompt = `You are planning a fix for issue %s.
Context: %s
Respond with step-by-step plan mapped to allowed files.`

	ApplyPrompt = `You must output ONLY a structured edit block.
Format:
kind: edit
filePath: <path>
oldText: |
  <exact old text>
newText: |
  <exact new text>
Context: %s`

	ReviewPrompt = `Review the following diff for rule compliance, secrets, and errors.
Diff: %s
Rules: %s
Respond with pass/fail and any required fixes.`

	PublishPrompt = `Generate a concise PR description from commit history and test results.
Commits: %s
Tests: %s`
)

func AnalyzePromptText(issue, context string) string {
	return fmt.Sprintf(AnalyzePrompt, issue, context)
}

func PlanPromptText(issue, context string) string {
	return fmt.Sprintf(PlanPrompt, issue, context)
}

func ApplyPromptText(context string) string {
	return fmt.Sprintf(ApplyPrompt, context)
}

func ReviewPromptText(diff, rules string) string {
	return fmt.Sprintf(ReviewPrompt, diff, rules)
}

func PublishPromptText(commits, tests string) string {
	return fmt.Sprintf(PublishPrompt, commits, tests)
}
