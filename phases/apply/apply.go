package phases

import "resolv/pkg/change"

func Apply() error {
	return change.ApplyStructuredEdit("main.go", "old", "new")
}
