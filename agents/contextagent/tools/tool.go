package tools

import "resolv/pkg/context"

func GrepFiles(paths []string, pattern string) ([]string, error) {
	return context.GrepFiles(paths, pattern)
}
func ParseAST(filePath string) (*context.Symbols, error) {
	return context.ParseAST(filePath)
}
