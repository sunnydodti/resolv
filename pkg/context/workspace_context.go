package context

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

func WorkspaceFileList(dir string, maxFiles int) string {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return fmt.Sprintf("(workspace unavailable: %v)", err)
	}
	var names []string
	count := 0
	for _, e := range entries {
		if e.IsDir() {
			continue
		}
		name := e.Name()
		if strings.HasSuffix(name, ".go") || strings.HasSuffix(name, ".md") || strings.HasSuffix(name, ".py") || strings.HasSuffix(name, ".json") {
			names = append(names, name)
			count++
			if count >= maxFiles {
				break
			}
		}
	}
	if len(names) == 0 {
		return "(no source files found)"
	}
	return strings.Join(names, ", ")
}

func WorkspaceSnippet(dir string, file string, maxChars int) string {
	b, err := os.ReadFile(filepath.Join(dir, file))
	if err != nil {
		return fmt.Sprintf("(read %s error: %v)", file, err)
	}
	s := string(b)
	if len(s) > maxChars {
		s = s[:maxChars] + "..."
	}
	return s
}
