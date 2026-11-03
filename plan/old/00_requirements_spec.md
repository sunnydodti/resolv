# Resolv — Requirement Specification (Platform/Language Independent)

## Problem Statement
Resolution pipeline for GitHub issues must: read issue, analyze root cause, plan fix, apply edits, build/test, review, publish PR, record audit state — all with budgets, exhaustion, and human gates.

## Required Phases (language-agnostic)
1. Analyze — extract issue intent + workspace context
2. Plan — generate structured resolution steps mapped to allowed files
3. Apply — execute structured edits with path validation
4. Build / Test — run user-configured commands with timeout/budget
5. Review — diff audit + rule compliance; fail → loop to Apply or Analyze
6. Publish — branch, commit, push, draft PR
7. Record — persist `.resolv/runs/<id>/state.json` + audit log

## Required Capabilities
- LLM call with structured tool support (function declarations / tool schema)
- Workspace context from repo source files (.go, .md, .py, .json, etc.) — not only docs
- Structured edit format with exact old/new text (JSON or YAML)
- Path/glob containment check against domain config
- Budget: max turns, token cap, wall-clock cap, max files, max diff lines
- Audit: append-only JSONL with hash chain, finalized after PR
- Failure routing: Build/Test fail → re-Apply; Review fail → Analyze; Turns >= max → Exhaustion Protocol (draft PR + audit + exit clean)
- Human gate before merge; dry-run / comment-only modes
- No auto-merge, no post-PR CI loop (v1 deferred)

## Constraints
- Trusted repos only (v1)
- OpenAI-compatible endpoint (phase 1); Anthropic (phase 2)
- No DB; JSON files only
- No container/microVM sandbox (v1 deferred)
- No semantic AST / vector store (v1 deferred)
- Cross-platform binary / runtime

## Interface Contracts (language-independent)
- Config: `resolv.yml` (build_cmd, test_cmd, lint_cmd, allowed/forbidden paths)
- State: JSON `state.json` (issue_ref, domain, phases_completed, pr_url, audit_path)
- Audit: `.resolv/audit.jsonl` (append-only, finalized after PR)
- LLM: HTTP POST with messages + optional tool declarations + generation config
- Tools: `apply_structured_edit(filePath, oldText, newText)`, `run_command(cmd)`, `read_file(path)`, `git_commit/branch/push`
