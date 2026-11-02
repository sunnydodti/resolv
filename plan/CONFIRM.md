# Resolv — Design Confirmed (updated from architecture spec)

## Terminology
- **Execution Stage** (not "Phase"): Analyze → Plan → Apply → Build/Test → Review → Publish → Record
- **Agent**: specialized actor with deterministic + AI-driven tool registry

## Stage-to-Agent Mapping (final)
1. **Analyze**: ContextAgent (GrepFiles, ParseAST) + DatabaseAgent (IntrospectSchema) + AI ExtractIssueIntent
2. **Plan**: PlannerAgent (CalculateTokenBudget, ValidateBoundaries, GenerateResolutionPlan AI)
3. **Apply**: GitAgent (CreateWorktree) + CodingAgent (ApplyStructuredEdit, ApplyGitDiffFallback)
4. **Build / Test**: ExecutionAgent (RunSandboxCommand, CheckBudget) + CodingAgent (GenerateHealingEdit AI)
5. **Review**: SecurityAgent (AuditDiffPaths, ScanEntropy) + ReviewAgent (EvaluateRuleCompliance AI)
6. **Publish**: GitAgent (CommitChanges, PushBranch) + PlatformAgent (OpenPullRequest, GeneratePRSummary AI, GenerateIssueGapsReport AI)
7. **Record**: TelemetryAgent (WriteAuditLog — continuous after each stage; audit finalized after PR)

## Failure Routing (updated)
- **Build/Test Failure (turns < max)** → loop back to **Apply** (re-change / self-heal)
- **Review Failure (turns < max)** → loop back to **Analyze / Plan** (re-evaluate strategy)
- **Turns >= max / budget exhausted** → **Exhaustion Protocol**:
  - Stage all progress → commit on `resolv-<id>`
  - Push branch → open **Draft PR** with **"Unresolved / Issue Gaps"** section (failure traces, attempted fixes, human action items)
  - Append audit log (`UNRESOLVED_DRAFT_PR_CREATED`)
  - Exit clean (no crash)

## Module Implementation Order (approved)
- **Module 1**: LLM Client & Prompt Gateway (`pkg/llm/`)
- **Module 2**: Context & Analysis Engine (`pkg/context/`)
- **Module 3**: Git Worktree & Change Engine (`pkg/git/`)
- **Module 4**: Sandbox Execution & Self-Healing (`pkg/agent/` budget + loop)
- **Module 5**: Platform Publisher & Draft Gap Generator (`pkg/platform/`)
- **Module 6**: Pipeline Orchestration & State Machine (`pkg/agent/` FSM driver + telemetry)

## Domain Config Commands (for Build/Test stage)
Repo-level fields from `domain.yml` / `/domains/<name>/config.yml`:
- `repos[].build_cmd`
- `repos[].test_cmd`
- `repos[].lint_cmd`

## Key Decisions Confirmed
- Config dir: `~/.resolv` (home), `RESOLV_CONFIG_DIR` override
- Credentials split: `resolv.yml` (refs) + `credentials.json` (values/env refs)
- Source-specific keys: `github.default`, `github.default_1`, etc.; domain folder scopes context but key naming stays source-based
- Draft PR default; no auto-merge
- Trusted repos; best-effort isolation; no cgo/frameworks/DB

Next: Confirm to proceed with **Module 1** (`pkg/llm/` — HTTP gateway + structured edit parsing) before implementing FSM.
