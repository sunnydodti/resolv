package pipeline

import (
	"resolv/pkg/session"
)

type FSM struct{}

func (f *FSM) Run(issueRef, domain string) error {
	dir := session.Dir(domain, "repo", issueRef)
	m, _ := session.LoadMetadata(dir)
	_ = m
	return nil
}
