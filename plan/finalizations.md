# Resolv – High‑Level Design Finalizations (v1)

## Language & Runtime
- **Go** chosen for fastest iteration, trivial cross‑compile, single static binary, stdlib‑first.
- No cgo, no heavy AST, no sandbox beyond best‑effort native; v1 = trusted repos only.

## Distribution
- GoReleaser → static binaries for linux/darwin/windows (amd64/arm64).
- Package managers (Homebrew/Scoop/winget) phase 2.

## Git & Repo Topology
- System `git >= 2.40` prerequisite (preflight check).
- One primary RW repo + N reference RO repos (cloned shallowly, never push).
- Platform adapters: **GitHub** + **local dir** only; GitLab/Bitbucket deferred.

## Autonomy
- **Draft PR** default; `--dry-run` / comment‑only modes explicit.
- Human gate before merge.

## LLM Egress
- OpenAI‑compatible HTTP client (`/v1/chat/completions`) only in v1.
- Anthropic added phase 2.

## Context & Patch
- **Text‑only** context: file reads + `git grep`/ripgrep. No tree‑sitter/cgo.
- Structured edit primary (`kind:"edit"`), unified‑diff fallback via `git apply --3way`.
- Path/glob validation before apply; ambiguity = refuse.

## State & Budgets
- JSON run state files (`.resolv/runs/<id>/state.json`). No DB.
- Budgets: `max_healing_turns`, token cap, cost cap, wall‑clock cap, max files, max diff lines.
- Baseline test run before patch; repeat‑patch fingerprint detection.

## Guard & Audit
- Internal entropy‑based secret redaction (prefix/token patterns).
- Path containment check against `domain.yml allowed/forbidden`.
- Append‑only JSONL audit log with hash‑chain; finalized **after** PR phase.

## What's Deferred (out of v1)
- GitLab, Bitbucket.
- Database introspection.
- Container/microVM sandbox.
- Untrusted/malicious repo defense.
- Auto‑merge, post‑PR CI loop, review‑comment handling.
- Semantic AST/call graphs, vector store.
- Commit signing, auto‑assign reviewers.
- TUI, OTel, Datadog sink.

## Core Packages (≈8, <300 LOC each)
- `cmd/resolv` – flags, wiring, exit codes.
- `internal/config` – YAML decode + validate.
- `internal/git` – worktree, commit, push, diff3way.
- `internal/context` – text grep, import heuristics.
- `internal/llm` – OpenAI‑compatible HTTP client.
- `internal/platform` – GitHub REST + local‑dir backend.
- `internal/guard` – redaction, path check, JSONL audit.
- `internal/agent` – 5‑phase FSM + budgets.

## Quick‑Start Skeleton
1. `cmd/resolv/main.go` – flag parse, config load, FSM init.
2. `internal/config/config.go` – strict YAML decode.
3. `internal/git/git.go` – git CLI wrappers.
4. `internal/llm/llm.go` – single‑endpoint HTTP client.
5. `internal/guard/guard.go` – entropy scan + path check.
6. `internal/agent/agent.go` – FSM driver + budget checks.
7. Minimal `resolv.yml` + `domain.yml` schemas (≈12 fields).
8. `go.mod` – only `gopkg.in/yaml.v3` (and optional `doublestar`).

All deps: ≤6 direct, no cgo, no frameworks, no DB, no TUI.

---
*Generated from the v1 constraint set: cross‑platform, single binary, trusted repos, draft PR, OpenAI‑compatible LLM, text context, JSON state.*