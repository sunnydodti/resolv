package pipeline

import (
	"fmt"
	"os"
	"path/filepath"
	"time"

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
	start := time.Now()
	fmt.Printf("\n[Pipeline] Starting resolution for %s / %s at %s\n", issueRef, domain, start.Format("15:04:05"))
	dir := session.Dir(domain, "repo", issueRef)
	var meta session.Metadata
	if resume || sessionExists(dir) {
		meta, _ = session.LoadMetadata(dir)
	} else {
		meta = session.Metadata{IssueID: issueRef, Domain: domain, CurrentStage: 1}
		_ = session.SaveMetadata(dir, meta)
	}

	fmt.Printf("\n[STAGE 1] Analyze...\n")
	if err := analyzePkg.Analyze(issueRef, domain); err != nil {
		return fmt.Errorf("analyze failed: %w", err)
	}
	fmt.Printf("[STAGE 2] Plan...\n")
	meta.CurrentStage = 2
	_ = session.SaveMetadata(dir, meta)
	plan := session.Plan{Steps: []string{"apply"}}
	_ = session.SavePlan(dir, plan)
	if err := planPkg.Plan(issueRef, domain); err != nil {
		return fmt.Errorf("plan failed: %w", err)
	}
	fmt.Printf("[STAGE 3] Apply...\n")
	meta.CurrentStage = 3
	_ = session.SaveMetadata(dir, meta)
	if err := applyPkg.Apply(issueRef, domain); err != nil {
		return fmt.Errorf("apply failed: %w", err)
	}
	meta.CurrentStage = 4
	_ = session.SaveMetadata(dir, meta)
	fmt.Printf("[STAGE 4] Apply edits...\n")
	if err := applyPkg.ApplyEdits(issueRef, domain); err != nil {
		return fmt.Errorf("apply edits failed: %w", err)
	}
	fmt.Printf("[STAGE 5] Build/Test...\n")
	meta.CurrentStage = 5
	_ = session.SaveMetadata(dir, meta)
	if err := buildPkg.Build(issueRef, domain); err != nil {
		return fmt.Errorf("build/test failed: %w", err)
	}
	fmt.Printf("[STAGE 6] Review...\n")
	meta.CurrentStage = 6
	_ = session.SaveMetadata(dir, meta)
	if err := reviewPkg.Review(issueRef, domain); err != nil {
		return fmt.Errorf("review failed: %w", err)
	}
	if !dryRun {
		fmt.Printf("[STAGE 7] Publish...\n")
		if err := publishPkg.Publish(issueRef, domain); err != nil {
			return fmt.Errorf("publish failed: %w", err)
		}
	} else if verbose {
		fmt.Println("Dry-run: skipped publish")
	}
	meta.CurrentStage = 7
	_ = session.SaveMetadata(dir, meta)
	fmt.Printf("[STAGE 8] Record...\n")
	if err := recordPkg.Record(domain, issueRef); err != nil {
		return fmt.Errorf("record failed: %w", err)
	}
	fmt.Printf("[STAGE 9] Audit...\n")
	if err := session.AppendAudit(dir, map[string]interface{}{
		"stage":        "record",
		"issue":        issueRef,
		"completed_at": time.Now().Format(time.RFC3339),
	}); err != nil {
		return fmt.Errorf("audit failed: %w", err)
	}
	elapsed := time.Since(start)
	fmt.Printf("\n[DONE] %d stages ran in %s\n", 9, elapsed)
	if verbose {
		fmt.Println("Pipeline complete")
	}
	return nil
}

func sessionExists(dir string) bool {
	_, err := os.Stat(filepath.Join(dir, "metadata.json"))
	return err == nil
}
