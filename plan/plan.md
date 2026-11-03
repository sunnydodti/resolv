# Resolv: High-Level Design (HLD) Specification

## 1. System Architecture & Core Objectives
Resolv is an autonomous, single-entry issue-to-PR CLI agent. It orchestrates deterministic tooling and AI-driven agents through a 7-stage state machine using LangGraph, multi-provider model routing via LiteLLM, structured schema validation through Instructor, and observability with Langfuse. Inter-stage state and artifacts are persisted locally for complete resumability, offline inspection, and hash-chained audit logging.

### Execution Strategy
*   **Deterministic Execution (No LLM):** Pure Python functions, shell/git commands, AST/regex parsing. Predictable, zero cost, zero latency.
*   **AI-Driven Execution (LLM):** Reasoning, intent extraction, planning, patch synthesis, review.

## 2. Technology Stack
*   **Runtime:** Python 3.11+, packaged via pipx.
*   **Orchestration:** LangGraph (FSM, cyclic self-healing, checkpointing).
*   **Multi-Provider Gateway:** LiteLLM (unified OpenAI-compatible payloads).
*   **Data Validation:** Instructor + Pydantic (strict JSON schema enforcement).
*   **Observability:** Langfuse (local Docker or cloud).

## 3. CLI Interface & Execution
`resolv <issue_reference> [flags]`

*   **Flags:**
    *   `--project <name>`: Target project configuration.
    *   `--analysis`: Halts after Stage 2 (Plan), exits.
    *   `--resume`: Resumes from last recorded state in `metadata.json`.
    *   `--dry-run`: Runs through Stage 5 (Review), bypasses Stage 6 (Publish/Push).
    *   `--verbose`: High-detail trace logs.
    *   `--max-healing-turns <int>`: (Default 3) Overrides self-healing budget.

## 4. Configuration Architecture
*   **Global (`resolv/config.yaml`):** Telemetry, default providers, global overrides.
*   **Project (`resolv/projects/<project_name>.yaml`):**
    *   `repos`: Primary/Reference repository paths, credentials, build/test/lint commands.
    *   `env_hooks`: `pre_command` and `post_command` (e.g., `poetry shell`, `source .env`).
    *   `settings`: `cleanup_worktree` (bool, default: `true`).

## 5. Persistent State & Storage
Data stored in `.resolv/sessions/<project_name>/<repo_issue_id>/`:
*   `metadata.json`: LangGraph state/cursor/status.
*   `context.json`: Structured inter-agent context.
*   `plan.json`: Structured roadmap.
*   `analysis.md` / `plan.md`: Human-readable inspection layers.
*   `audit.log`: Cryptographic hash-chained trail.

## 6. Execution Flow
1.  **Stage 0: Init:** Create workspace/session, resolve mappings.
2.  **Stage 1: Analyze:** Ingest issue, AST/semantic exploration, schema extraction.
3.  **Stage 2: Plan:** Synthesize strategy, budget tokens, emit `plan.json`.
4.  **Stage 3: Apply:** Create worktree, synthesize edits/patches.
5.  **Stage 4: Build/Test:** Self-healing loop (max 3 turns).
6.  **Stage 5: Review:** Audit diffs, entropy scan, compliance check.
7.  **Stage 6: Publish:** Sign/Commit, Push, Open PR/MR.
8.  **Stage 7: Record:** Audit logs, telemetry flush.

### Fail-Safe Protocol
If Stage 4 reaches 3 attempts, the agent stops, saves observations, commits local state, and opens a Draft PR with an "Issue Gaps" report.

## 7. Sub-Agent Capability Matrix
*   **GitAgent:** Workspace/version control.
*   **ContextAgent:** Codebase comprehension (CodeGraph, GitHistory).
*   **PlannerAgent:** Roadmap generation.
*   **CodingAgent:** Patch synthesis, self-healing.
*   **ExecutionAgent:** Sandbox runner.
*   **SecurityAgent:** Entropy/credential scanning.
*   **ReviewAgent:** Guideline compliance.
*   **DatabaseAgent:** Schema/Migration introspection.
*   **PlatformAgent:** Remote integration (GitHub/GitLab).
*   **TelemetryAgent:** Audit/Langfuse logging.
