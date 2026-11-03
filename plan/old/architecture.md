# Resolv Multi-Agent Architecture & Phase Execution Design Spec

## Phase Names (final)
1. **Analyze** — ContextAgent (grep/parse) + DatabaseAgent (schema); AI: ExtractIssueIntent
2. **Plan** — PlannerAgent; AI: GenerateResolutionPlan; det: ValidateBoundaries, CalculateTokenBudget
3. **Apply** — GitAgent (worktree) + CodingAgent (structured edit / git apply --3way fallback)
4. **Build / Test** — ExecutionAgent (sandbox command + budget); CodingAgent (GenerateHealingEdit on failure); loop back to Apply if fail + turns < max
5. **Review** — SecurityAgent (AuditDiffPaths + ScanEntropy) + ReviewAgent (EvaluateRuleCompliance, AI); fail → loop to Analyze if turns < max
6. **Publish** — GitAgent (commit/sign/push) + PlatformAgent (draft PR REST + PR summary/gaps AI)
7. **Record** — TelemetryAgent writes `.resolv/runs/<id>/state.json` after each phase; audit `.resolv/audit.jsonl` finalized after PR

## Failure Routing
- Build/Test fail (turns < max) → **Apply** (re-change)
- Review fail (turns < max) → **Analyze** (re-think / new plan)
- Turns >= max → **Exhaustion Protocol**: stage all, push `resolv-<id>`, open Draft PR with Unresolved/Issue Gaps summary, audit, exit clean

## Agents & Tool Registry (lean, stdlib-first)
- **ContextAgent**: `GrepFiles`, `ParseAST` (det)
- **DatabaseAgent**: `IntrospectSchema` (det)
- **PlannerAgent**: `CalculateTokenBudget`, `ValidateBoundaries` (det), `GenerateResolutionPlan` (AI)
- **GitAgent**: `CreateWorktree`, `CommitChanges`, `PushBranch` (det)
- **CodingAgent**: `ApplyStructuredEdit`, `ApplyGitDiffFallback` (det); `GenerateHealingEdit` (AI, on test failure)
- **ExecutionAgent**: `RunSandboxCommand`, `CheckBudget` (det)
- **SecurityAgent**: `AuditDiffPaths`, `ScanEntropy` (det)
- **ReviewAgent**: `EvaluateRuleCompliance` (AI)
- **PlatformAgent**: `OpenPullRequest`, `GeneratePRSummary`, `GenerateIssueGapsReport` (det + AI)
- **TelemetryAgent**: `WriteAuditLog` (det JSONL)

## Build/Test / Lint Config (domain/repo level)
Repo-level `build_cmd`, `test_cmd`, `lint_cmd` from domain config. ExecutionAgent runs user-provided command via `os/exec.CommandContext` with timeout.

## State & Budget
- `max_healing_turns`: max loop iterations (Apply→Build/Test→Review)
- `token_cap`, `cost_cap`, `wall_clock_cap`
- `state.json` updated continuously after each phase; audit finalized after Publish.
