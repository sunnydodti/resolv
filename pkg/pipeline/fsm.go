package pipeline

import (
	"fmt"
	"os"
	"path/filepath"
	analyzePkg "resolv/phases/analyze"
	applyPkg "resolv/phases/apply"
	buildPkg "resolv/phases/build"
	planPkg "resolv/phases/plan"
	publishPkg "resolv/phases/publish"
	recordPkg "resolv/phases/record"
	reviewPkg "resolv/phases/review"
	"resolv/pkg/session"
)

type FSM struct{}

func (f *FSM) Run(issueRef, domain string, resume bool, dryRun bool, verbose bool, maxTurns int) error {
	dir := session.Dir(domain, "repo", issueRef)
	var meta session.Metadata
	if resume || sessionExists(dir) {
		meta, _ = session.LoadMetadata(dir)
	} else {
		meta = session.Metadata{IssueID: issueRef, Domain: domain, CurrentStage: 1}
		_ = session.SaveMetadata(dir, meta)
	}

	_ = analyzePkg.Analyze()
	meta.CurrentStage = 2; _ = session.SaveMetadata(dir, meta); _ = session.SavePlan(dir, session.Plan{Steps: []string{"apply"}})
	_ = planPkg.Plan()
	meta.CurrentStage = 3; _ = session.SaveMetadata(dir, meta)
	_ = applyPkg.Apply()
	meta.CurrentStage = 4; _ = session.SaveMetadata(dir, meta)
	_ = buildPkg.Build()
	meta.CurrentStage = 5; _ = session.SaveMetadata(dir, meta)
	_ = reviewPkg.Review()
	if !dryRun {
		meta.CurrentStage = 6; _ = session.SaveMetadata(dir, meta)
		_ = publishPkg.Publish()
	} else if verbose {
		fmt.Println("Dry-run: skipped publish")
	}
	meta.CurrentStage = 7; _ = session.SaveMetadata(dir, meta); _ = recordPkg.Record(domain, issueRef); _ = session.AppendAudit(dir, map[string]interface{}{"stage":"record","issue":issueRef})
	if verbose {
		fmt.Println("Pipeline complete")
	}
	return nil
}

func sessionExists(dir string) bool {
	_, err := os.Stat(filepath.Join(dir, "metadata.json"))
	return err == nil
}
