# Resolv – v1 HLD Finalizations

This folder contains the finalized high‑level design decisions and a minimal starter skeleton for the Resolv autonomous CLI agent (v1).

## Contents
- `finalizations.md` – locked choices: Go language, single static binary, trusted‑repo assumption, GitHub + local platform adapters, text‑only context (no AST), OpenAI‑compatible LLM client, JSON run state, budgets & FSM, guard/redaction, deferred items.
- *(Other files may be added as the implementation begins.)*

## Quick‑Start (if you want to hack today)
1. Install Go 1.24+.
2. `go mod init resolv && go get gopkg.in/yaml.v3`
3. Run `go run ./cmd/resolv --issue RESOLV-123 --repo <path> --dry-run` (starter scaffold not yet included; see `finalizations.md` for the intended file layout).

## Goals
- Iterate fast: ~seconds compile, single binary, minimal deps.
- v1 scope: one primary repo + read‑only reference repos, draft PR, text context, budgets, trusted‑repo only.
- Deferred: GitLab/Bitbucket, DB introspection, container sandbox, AST/semantic, signing, auto‑merge.

## Notes
- All design is captured in `finalizations.md`; no code is provided here yet.
- The plan is to keep dependencies ≤6, no cgo, no frameworks, no DB, no TUI.