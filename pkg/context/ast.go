package context

import (
	"fmt"
	"os"
	"regexp"
	"strings"
)

type Symbols struct {
	Functions []string `json:"functions"`
	Types     []string `json:"types"`
	Imports   []string `json:"imports"`
}

func ParseAST(filePath string) (*Symbols, error) {
	data, err := os.ReadFile(filePath)
	if err != nil {
		return nil, fmt.Errorf("read %s: %w", filePath, err)
	}
	s := &Symbols{}
	funcRe := regexp.MustCompile(`func\s+([A-Z][A-Za-z0-9_]*)`)
	typeRe := regexp.MustCompile(`type\s+([A-Z][A-Za-z0-9_]*)`)
	importRe := regexp.MustCompile(`"([^"]+)"`)
	for _, m := range funcRe.FindAllStringSubmatch(string(data), -1) {
		s.Functions = append(s.Functions, m[1])
	}
	for _, m := range typeRe.FindAllStringSubmatch(string(data), -1) {
		s.Types = append(s.Types, m[1])
	}
	for _, m := range importRe.FindAllStringSubmatch(string(data), -1) {
		line := m[1]
		if !strings.Contains(line, ".") && len(line) > 0 {
			s.Imports = append(s.Imports, line)
		}
	}
	return s, nil
}
