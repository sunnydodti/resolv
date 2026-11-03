# Working Flow Plan — Resolv End-to-End

## Analysis (current state)
- Config: `~/.resolv/resolv.yml`, `domain.yml`, `credentials.json` (good).
- Setup (`pkg/cli/setup.go`): registers repos (`primary`/`reference`) into domain config (good).
- Pipeline (`pkg/pipeline/fsm.go`): creates session dirs (`.resolv/sessions/<domain>_repo_<issue>`), runs stages sequentially (good structure).
- Honest fixes applied: `pr.go` (auth + status check), `apply/apply.go` (structured edits + commit only when edits > 0), `analyze/analyze.go` (correct URL split), `record/record.go` (pending default), `build/build.go` (attempts real commands).
- Gaps blocking real use:
  1. **No repo clone / checkout**: pipeline assumes repo is in CWD (`.`); never reads `domain.yml` repos or clones into workspace.
  2. **Session repo name hardcoded**: `session.Dir(domain, "repo", issueRef)` ignores actual repo path from config.
  3. **Edit/apply on CWD**: `applyAllEdits` writes relative to `.`; if user runs from wrong dir, edits miss target.
  4. **Build/test ignores domain config**: reads no `build_cmd`/`test_cmd` from `repo.Config` or domain entry.
  5. **Publish branch/push on CWD**: `pr.go` does `git checkout -b` / `git push` in `.` without confirming it’s the cloned repo.
  6. **Plan broken / unverified**: `plan.go` parses incorrectly (still unverified per spec); apply depends on it.
  7. **Audit meaningless**: writes only stage name, no PR URL / branch / edit count / errors.

## Required for "wired up and working"
1. **Workspace creation**: pipeline creates workspace directory for run (e.g., `.resolv/workspaces/<domain>_<repo>` or session dir + clone into it).
2. **Clone / checkout primary repo**: read `DomainEntry.Repos["primary"]` from `domain.yml`; if missing, fall back to CWD; if present and workspace empty, `git clone --depth 1` then `git checkout` / `git worktree` if needed.
3. **Operate on workspace**: all phases (analyze grep, apply edits, build, commit, push) must set `cmd.Dir = workspaceDir` or work with absolute paths.
4. **Domain commands honored**: `build/build.go` reads `Repo.BuildCmd` / `Repo.TestCmd` from config; defaults to `go build ./...`.
5. **Publish from workspace**: `pr.go` operates in workspace dir; pushes branch; constructs PR URL from repo source (`github.com/owner/repo`).
6. **Truthful audit + record**: audit logs PR URL, branch, edit count, errors; record sets `completed = true` only when PR URL present or verified edit+build success.

## Implementation order
- Step 1: Workspace / clone helper (`pkg/workspace` or modify `pkg/session`).
- Step 2: Pipeline `fsm.go` — create workspace, clone if needed, pass dir to all phases.
- Step 3: `phases/analyze/analyze.go` — grep / AST in workspace.
- Step 4: `phases/apply/apply.go` — apply edits relative to workspace; commit from workspace.
- Step 5: `phases/build/build.go` — read repo config, run in workspace.
- Step 6: `pkg/platform/pr.go` — run git branch/push in workspace; use correct repo URL for PR endpoint.
- Step 7: `phases/record/record.go` + audit — truthful status.
- Step 8: Verify with `resolv init`, `resolv setup`, `resolv ... --dry-run`.

## Success criteria
- `resolv setup mydomain` saves repo to `domain.yml`.
- `resolv ...` clones/checks out repo into workspace.
- Analyze finds real files (not just `.`); edit applies to cloned file.
- Build succeeds using configured command.
- PR stage either creates PR (with token) or clearly returns error (no false success).
- Record writes `pending` until verified; audit contains PR URL / errors.
