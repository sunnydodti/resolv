# Implementation Plan — Single-Entry CLI + Session Storage

1. Session storage: create `.resolv/sessions/` loader/saver (metadata, context, plan, audit).
2. CLI command: `cmd/resolv/main.go` — register `resolv <issue>` with flags (`--domain`, `--analysis-only`, `--resume`, `--dry-run`, `--verbose`, `--max-healing-turns`).
3. Phase dirs: `phases/analyze/`, `phases/plan/`, `phases/apply/`, `phases/build/`, `phases/review/`, `phases/publish/`, `phases/record/` (stubs linking to M1-M6 libs).
4. Agent dirs: `agents/contextagent/`, `agents/planneragent/`, `agents/gitagent/`, `agents/codingagent/`, `agents/securityagent/`, `agents/reviewagent/`, `agents/platformagent/`, `agents/telemetryagent/` (stubs/tool refs).
5. Wire pipeline: `resolv <issue>` calls M1-M6 sequentially using session load/resume; save session state after Analyze/Plan and at exhaustion.
6. Commit + review.
