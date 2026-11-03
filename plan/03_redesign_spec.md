# Resolv — Redesign Specification (Platform/Language Independent)

## Design Principles
1. **Language-independent interface**: All contracts (LLM, agent registry, workspace, edit, audit, state) defined as abstract interfaces, not tied to Go types or Python classes.
2. **State-machine first**: Pipeline is an explicit finite-state machine (FSM) with defined states, allowed transitions, and guard conditions. Not hidden framework loops.
3. **Tool registry**: Agents expose capabilities by name; pipeline calls them by name. Not direct function imports across phases.
4. **Audit/state as interface**: Append-only audit log and JSON state files defined by schema; storage mechanism (file, DB, external) interchangeable.
5. **LLM abstraction**: Transport layer handles endpoint, message format, tool schema, retry/backoff, timeout, rate limit. Pipeline never builds `map[string]interface{}` directly.
6. **Workspace context as interface**: Returns list of files and snippets, independent of `os.ReadDir` or Python `os.listdir`. Source `.go` files must be included.
7. **Structured edit format**: JSON with fixed keys (`file`, `old`, `new`) parsed by JSON parser, not regex. Keys must be consistent between prompt, parser, and tool execution.
8. **Failure routing explicit**: State diagram defines loop conditions (Build/Test fail → Apply; Review fail → Analyze; Turns >= max → Exhaustion).

## Abstract Component Model
- **LLMTransport**: Call(messages, tools?, generationConfig?) → Response(content, toolCalls?, usage?) + Retry/Backoff/Timeout
- **AgentRegistry**: Register(name, capabilities[]); Get(name) → AgentCapabilities
- **AgentCapability**: Name(string) + Inputs(schema) + Outputs(schema) + Execute(context) → Result
- **PipelineFSM**: States(Analyze, Plan, Apply, BuildTest, Review, Publish, Record); Transitions(); Guards(); Actions()
- **EditInterface**: ParseJSON(resp) → []Edit(file, old, new); ValidatePath(file, workspace); Execute(edit) → error
- **AuditInterface**: Append(event) → auditLog; Finalize() → finalizedLog; Schema(version, timestamp, eventType, hash)
- **StateInterface**: Load(id) → State; Save(id, state) → file; Schema(issue_ref, domain, phases_completed[], pr_url, audit_path)
- **WorkspaceInterface**: List(repoRoot?, max?) → []FileInfo; ReadSnippet(file, maxChars?) → string

## States & Transitions (abstract)
1. Analyze → (on success) Plan
2. Plan → (on success) Apply
3. Apply → (on success) BuildTest
4. BuildTest:
   - Pass → Review
   - Fail (turns < max) → Apply (loop back)
5. Review:
   - Pass → Publish
   - Fail (turns < max) → Analyze
6. Publish → Record
7. Record → (always) Audit Finalize; Exit
8. Any: Turns >= max → Exhaustion (Publish Draft, Finalize Audit, Exit clean)

## Tool Schema (abstract interface — language independent)
```
Tool: apply_structured_edit
  Inputs: filePath (string), oldText (string), newText (string)
  Outputs: success/error
Tool: run_command
  Inputs: cmd (string array/string), timeout (duration/int)
  Outputs: stdout, stderr, exitCode
Tool: read_file
  Inputs: path (string)
  Outputs: content (string)
Tool: git_commit
  Inputs: message (string), branch (string)
  Outputs: hash, error
Tool: open_pr
  Inputs: title, body, headBranch, baseBranch
  Outputs: url, number
```

## Interface Schema Example (JSON, independent of language types)
```
AgentRegistry:
  { "codingagent": ["apply_structured_edit", "read_file"],
    "gitagent": ["create_worktree", "commit_changes", "push_branch"],
    "contextagent": ["grep_files", "parse_ast"],
    "planneragent": ["generate_resolution_plan", "validate_boundaries", "calculate_token_budget"],
    "securityagent": ["audit_diff_paths", "scan_entropy"],
    "telemetryagent": ["write_audit_log"] }
```

## Redesign Implementation Steps (independent of language choice)
1. Define abstract interfaces above in chosen language (Go, Python, TypeScript, etc.).
2. Implement LLMLayer (transport + retry + tool schema + message construction) as separate package/module.
3. Implement WorkspaceLayer (repo root detection + file listing + snippet extraction) to include `.go` and source files.
4. Implement AgentRegistry (map/dict of agent capabilities) that pipeline phases reference by name.
5. Redesign Analyze phase to pass workspace snippets (not just filenames) to LLM.
6. Redesign Plan phase to output JSON with `steps`, `suggested_fix`, `affected_files`; parse with JSON parser.
7. Redesign Apply phase to receive workspace file list + edit array; execute via `AgentRegistry.get("codingagent").execute(edit)`.
8. Add retry/backoff logic to LLMLayer (not just timeout).
9. Ensure AuditInterface and StateInterface are called by FSM, not by individual phases independently.
10. Update workspace context interface to read from repo root when workspaceDir is set, not just current directory `.`.

## Final Options (language-independent choice)
- **Option A (Go native redesign)**: Implement abstract interfaces in Go; reuse existing `pkg/` packages as concrete implementations; keep static binary; add LLMLayer + AgentRegistry properly.
- **Option B (Python sidecar / embedded framework)**: Implement abstract interfaces in Python using LangGraph or Pydantic AI; Go pipeline calls Python via subprocess/gRPC; keep audit/state in `.resolv/` format.
- **Option C (TypeScript/Node)**: If team prefers TypeScript; use Mastra for agent framework and keep audit/state interfaces same.
- **Option D (Custom abstract only)**: Design interfaces without framework dependency; implement concrete agents in chosen language; allows future framework swap.
