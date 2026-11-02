package context

import (
	"fmt"
	"path/filepath"
	"strings"
)

func ValidateBoundaries(fileList []string, allowedPaths []string) error {
	allowed := make(map[string]bool)
	for _, a := range allowedPaths {
		abs, err := filepath.Abs(a)
		if err != nil {
			abs = a
		}
		allowed[abs] = true
	}
	for _, f := range fileList {
		abs, err := filepath.Abs(f)
		if err != nil {
			abs = f
		}
		ok := false
		for a := range allowed {
			if strings.HasPrefix(abs, a+string(filepath.Separator)) || abs == a {
				ok = true
				break
			}
		}
		if !ok {
			return fmt.Errorf("boundary violation: %s outside allowed paths", f)
		}
	}
	return nil
}
