# /plan — Preserved Requirements & Redesign (Platform/Language Independent)

Created: Wed Nov 04 2026.
Status: preserved from v1 pipeline (issue #1 / resolv); gap analysis from pipeline logs (Nov 03); framework options evaluated; redesign spec language-independent.

Files:
- 00_requirements_spec.md — interface contracts, phases, budget, audit, failure routing
- 01_gap_analysis.md — parse failures, missing source context, empty LLM outputs, tool declaration errors
- 02_framework_options.md — 7 options evaluated; recommendation = custom state-machine or embed framework
- 03_redesign_spec.md — abstract interfaces + state transitions + tool schema + implementation steps

Key preserved points (language-independent):
- Pipeline phases: Analyze → Plan → Apply → Build/Test → Review → Publish → Record
- Structured edit format (file, old, new) with JSON parser, not regex
- Workspace context must include source `.go` files, not only docs
- Audit/state: `.resolv/` JSON/JSONL files, finalized after PR
- Failure routing explicit (loop rules, exhaustion protocol)
- LLM transport with retry, timeout, tool schema, generation config
- Human gate / dry-run explicit; no auto-merge

Next decision needed: choose implementation language (Go, Python, TypeScript) and concrete framework if any. Redesign spec works for all.
