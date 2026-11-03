# Resolv — Single-Entry Pipeline CLI & Persistent Session Spec

## Entry
- `resolv <issue_ref> [flags]` — one command, no per-stage CLI.
- Flags: `--analysis-only`, `--resume`, `--dry-run`, `--verbose`, `--max-healing-turns`, `--domain <csv>`
- `--domain` CSV (e.g., `resolv,expense,finance`); first used for now.

## Session Storage (disk-based)
- Path: `.resolv/sessions/<domain>_<repo>_<issue>/`
- Files: `metadata.json`, `context.json`, `plan.json`, `audit.log` (jsonl)
- Resume: load `metadata.json`; pick up stage pointer.

## Pipeline Stages (7)
1. Analyze → 2. Plan → 3. Apply → 4. Build/Test → 5. Review → 6. Publish → 7. Record
- Failure routing per design: Build/Test → Apply; Review → Analyze/Plan; exhaustion → stage + draft PR + gaps + audit + exit.

## Directory Organization
- `phases/<stage>/` — stage-specific logic
- `agents/<agent>/` — agent definitions
- `agents/<agent>/tools/` — deterministic tool implementations
- Existing `pkg/` libraries (llm, context, change, agent, platform, pipeline) referenced, not moved.

## Decisions Confirmed
- No manual per-stage commands.
- Session IDs derived from domain/repo/issue.
- Audit JSONL (hash-chained if implemented).
- Init/setup remain; may need updates for pipeline inputs.
