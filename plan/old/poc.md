# Resolv — Minimal POC Agent Flow (Plan) — RENAMED PHASES

## Phase names (user-approved)
1. **Diagnose** — read issue, grep context → LLM root-cause
2. **Repair** — LLM edit (`kind:"edit"`) → guard → apply / fallback
3. **Validate** — run repo test command; pass/fail
4. **Publish** — branch `resolv-<id>` → push → draft PR (`POST /repos/.../pulls`)
5. **Record** — `runs/<id>/audit.jsonl`; finalize after PR

## Scope (locked)
- GitHub adapter + local dir only; draft PR default; no TUI/OTel.
- `resolv init` / `resolv setup` already working.
- LLM: OpenAI-compatible HTTP (`/v1/chat/completions`).
- Context: file reads + `git grep` text only; no tree-sitter.
- State: `.resolv/runs/<id>/state.json`; budgets (`max_healing_turns`, token cap, wall-clock).
- Guard: path/glob check + entropy-based redaction.

## Implementation order (pending approval)
1. `pkg/agent/` — FSM (Diagnose→Repair→Validate→Publish→Record) + budgets
2. `pkg/llm/` — HTTP client + edit parse
3. `pkg/git/` — worktree / grep / apply
4. `pkg/guard/` — path + redaction
5. `pkg/platform/` — GitHub REST (draft PR)
6. Wire `cmd/resolv/run`

## Key constraints (do not change without ask)
- Go 1.24, ≤6 direct deps, `yaml.v3`, `cobra`, no cgo/DB/TUI.
- Config dir = `%USERPROFILE%\.resolv`; `RESOLV_CONFIG_DIR` override.
- Credentials split: `resolv.yml` (refs) + `credentials.json` (values/env refs).
- Trusted repos only.
