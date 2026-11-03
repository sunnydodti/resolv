# Plan: Remove All Stubs — Real Resolv Run on sunnydodti/resolv Issue #1

Status: Plan only. No repo changes applied yet.
Requires user approval before any file writes / git changes.

## Target
- Issue: https://github.com/sunnydodti/resolv/issues/1
- Domain: resolv
- Outcome: Real PR created on the repo (not just a fake `fmt.Printf`).

## Phase 1: Auth / Setup (Plan + Setup)
1. Configure `pkg/credentials/resolver.go` with real GitHub token (for PR creation, branch push).
2. Configure `pkg/llm/client.go` / loader with real LLM endpoint + API key.
3. Verify `resolv/pkg/config/loader.go` loads secrets from env/file, not empty defaults.
4. Add `.env` or `resolv-config.json` to repo root (will ask before committing).

## Phase 2: Pipeline Fix (cmd + pkg/pipeline)
5. `cmd/resolv/main.go`: Stop discarding `fsm.Run(...)` error (`_ =` → `if err := ...`).
6. `pkg/pipeline/fsm.go`:
   - Remove duplicate `return nil` (line 65/66).
   - Change all `_ = phase.X()` to real error propagation: `if err := phase.X(); err != nil { return err }`.
   - Replace fake stage messages with progress messages only after real work completes.
7. `pkg/pipeline/telemetry.go`: Wire to real metrics, not empty struct.

## Phase 3: Real Phase Implementations
8. `phases/analyze/analyze.go`: Real LLM call using `pkg/llm`; parse issue payload; return structured analysis (not `nil` immediately). Remove ignored `context.GrepFiles` / `ParseAST` unless needed.
9. `phases/plan/plan.go`: Real resolution plan generation; save to `session.Plan` properly.
10. `phases/apply/apply.go`: Call `codingagent` to make real file edits based on plan.
11. `phases/apply/apply.go` (edits): Apply `pkg/change/edit.go` features to create actual diffs.
12. `phases/build/build.go`: Execute `go build` / `go test` via `exec.Command`, not stub.
13. `phases/review/review.go`: Call `reviewagent` with real results; block pipeline on failure.
14. `phases/publish/publish.go`: Real `platform.OpenPullRequest` using `pkg/platform/pr.go` (use GitHub API or `gh` CLI), not just `fmt.Printf`.
15. `phases/record/record.go`: Write real audit/session log.
16. `phases/audit` (`fsm.Run`): Real append to audit file.

## Phase 4: Agent Stubs (Remove No-Ops)
17. `agents/codingagent/agent.go` + `tools/`: Implement file reading, edit application, diff validation.
18. `agents/planneragent/agent.go`: Real plan generation with task decomposition.
19. `agents/reviewagent/agent.go`: Real review logic (lint, test results, security checks).
20. `agents/securityagent/agent.go`: Remove empty agent or wire to basic security scan.
21. `agents/telemetryagent/agent.go`: Remove or wire to real logging.
22. `agents/gitagent/agent.go`: Real git operations (branch, commit, push) instead of empty stubs.
23. `agents/platformagent/agent.go`: Real PR creation / branch push.
24. `agents/contextagent/agent.go`: Real repo context extraction.

## Phase 5: Real Issue Resolution
25. Parse `https://github.com/sunnydodti/resolv/issues/1` payload.
26. Generate code fix using LLM + `codingagent`.
27. Create branch (`resolv-fix`), commit edits.
28. Push to remote (requires token from Phase 1).
29. Open real PR (`isDraft=true` based on user command or config) via GitHub.
30. Save session metadata (`pkg/session/metadata.go`) with real stage tracking.

## Phase 6: Validation
31. Build (`go build`) passes.
32. `go test ./...` passes.
33. Real PR URL is returned (not just `"Auto PR"`).
34. Audit log contains real stage timestamps.

## Constraints / Rules
- READONLY ONLY on git: No commits/pushes without explicit user approval for each step.
- I will not persist `.git` changes without written approval.
- I will build/test but will stop before `git push` / PR creation unless confirmed.

## Next Action Needed From You
Confirm which steps to execute first (e.g., start with Phase 1 auth setup + Phase 2 pipeline fix, or full implementation). Once approved, I will apply edits file-by-file and report git status before any `git` commands.
