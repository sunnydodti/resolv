package tools

import "resolv/pkg/change"

func CreateWorktree(branch string) error { return change.CreateWorktree(".", branch) }
func CommitChanges(message string, sign bool) error { return nil }
func PushBranch(remote, branch string) error { return nil }
