package context

import (
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
)

func GrepFiles(paths []string, pattern string) ([]string, error) {
	re, err := regexp.Compile(pattern)
	if err != nil {
		return nil, fmt.Errorf("bad regex: %w", err)
	}
	var hits []string
	for _, p := range paths {
		infos, err := os.ReadDir(p)
		if err != nil {
			continue // skip unreadable dirs
		}
		for _, info := range infos {
			if info.IsDir() {
				continue
			}
			name := info.Name()
			if strings.HasSuffix(name, ".go") || strings.HasSuffix(name, ".md") {
				data, err := os.ReadFile(filepath.Join(p, name))
				if err != nil {
					continue
				}
				if re.Match(data) {
					hits = append(hits, filepath.Join(p, name))
				}
			}
		}
	}
	return hits, nil
}
