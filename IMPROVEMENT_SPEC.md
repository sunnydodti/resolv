# Resolv Pipeline Failure — Analysis & Fix Spec
Branch: dev  Command: git status (clean, on dev)

---

## 1. What went wrong (replay of output)
- Pipeline finished 9 stages in ~9s / ~6s.
- Analyze returned generic `Unknown / medium`.
- Plan produced broken `plan.json`: `{"steps":["["],...}`.
- Apply produced 0 edits; `applyAllEdits` is a no-op loop.
- Build/test skipped despite configured commands.
- Publish printed `[Publish] PR created successfully` but actual response was `message:Bad credentials status:401`. No PR/MR created.
- Record wrote `"completed":true` regardless.
- Audit log has 2 entries (reruns) with no error context.

---

## 2. Impact analysis
| Component | Issue | Impact | Severity |
|---|---|---|---|
| `pkg/platform/pr.go` | `loadResolver` reads `credentials.json` from `.`, ignores HTTP 401, ignores token errors, pushes branch blindly | **False success** — user thinks PR created; auth failure hidden; branch pollution | Critical |
| `phases/apply/apply.go` | `applyAllEdits` never writes files; `parseEditObject` ignores old/new; `commitChanges` always runs | **Zero code changes** despite LLM output; false commit | Critical |
| `phases/analyze/analyze.go` | `loadIssuePayload` splits URL incorrectly (`parts[0]` = full URL) | **No real issue text** fetched; root-cause always unknown | High |
| `phases/plan/plan.go` | `parsePlan` splits on `[` incorrectly for array values | **Broken plan** — steps become `[`; apply has nothing to do | High |
| `phases/record/record.go` | Always writes `Status: "completed"`, never checks edits/PR/build | **False closure** — issue marked resolved with zero work | High |
| `phases/build/build.go` | Hardcodes `go build .` / `go test -count=1 -timeout=30s`; ignores domain config | **Build/test commands from setup ignored** | Medium |
| `phases/review/review.go` | Only prints strings; loads plan but does nothing with it | **No validation** of syntax/changes/tests | Medium |
| `pkg/pipeline/fsm.go` | Saves `current_stage:7` even when publish failed; audit only writes stage name | **No failure chain** — audit useless for debugging | Medium |

---

## 3. Best way forward (prioritized)
1. **Fix PR/auth path first** — without truthful publish, nothing else matters. Make `createPR` check `resp.StatusCode`, resolve token from `~/.resolv/credentials.json`, and return errors.
2. **Make apply actually edit** — wire `applyAllEdits` to `change.ApplyStructuredEdit`; fix `parseEditObject` for `old`/`new`; only commit if edits applied.
3. **Fix analysis input** — correct `loadIssuePayload` parsing so LLM gets real issue text.
4. **Fix plan parsing** — robust JSON array extraction so steps are real.
5. **Make record truthful** — record `completed` only if PR URL exists OR (edits > 0 AND build passed); include `status: failed/published/partial`.
6. **Make build/test use setup config** — read `config.yml` or pass domain commands.
7. **Improve audit** — log error strings, branch, PR URL, edit count.

---

## 4. Implementation plan (current branch dev)
- [x] Spec written (this file)
- [ ] `pkg/platform/pr.go` — loadResolver path + status check + token resolve
- [ ] `phases/apply/apply.go` — real edit application + old/new parsing
- [ ] `phases/analyze/analyze.go` — correct URL parsing
- [ ] `phases/plan/plan.go` — robust array split
- [ ] `phases/record/record.go` — conditional status
- [ ] `phases/build/build.go` — use domain config
- [ ] `phases/review/review.go` — minimal syntax/import check
- [ ] Verify with `resolv init` + `resolv setup` + `resolv ...` (will still 401 on PR, but now surfaces correctly; edits will apply if LLM responds)
