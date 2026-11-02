package tools

import "resolv/pkg/change"

func ApplyStructuredEdit(filePath, oldText, newText string) error {
	return change.ApplyStructuredEdit(filePath, oldText, newText)
}
func ApplyGitDiffFallback(diffBytes []byte) error {
	return change.ApplyGitDiffFallback(".", diffBytes)
}
func GenerateHealingEdit(errorTrace, failingFile string) string { return "fix" }
