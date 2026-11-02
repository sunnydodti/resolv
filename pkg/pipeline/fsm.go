package pipeline

import (
	"os"
	"path/filepath"
	"resolv/pkg/session"
)

type FSM struct{}

func (f *FSM) Run(issueRef, domain string, resume bool, dryRun bool, verbose bool, maxTurns int) error {
	dir := session.Dir(domain, "repo", issueRef)
	if resume || sessionExists(dir) {
		_, _ = session.LoadMetadata(dir)
	}
	// Sequential: Analyze → Plan → Apply → Build/Test → Review → Publish → Record
	_ = dir
	_ = dryRun
	_ = verbose
	_ = maxTurns
	return nil
}

func sessionExists(dir string) bool {
	_, err := os.Stat(filepath.Join(dir, "metadata.json"))
	return err == nil
}
