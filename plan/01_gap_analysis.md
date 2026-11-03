# Resolv — Gap Analysis (from Pipeline Logs)

## Critical Failures (Nov 03 runs)
- Analyze: returns content but parse fails (`parseAnalysis` expects literal "Root cause:" / "Severity:" — LLM uses markdown headings; parsing misses them)
- Plan: `parsePlan` uses comma-split (`splitLines`) — breaks multi-word steps; returns 1 step instead of 4; uses `strings` not JSON parser
- Apply: returns `len=0`; `parseEdits` breaks on multiline JSON strings (findClosingBrace fails); file names hallucinated (`STUB_REMOVAL_PLAN.md` instead of workspace files); no path validation before edit; no workspace source `.go` files included in LLM context
- Apply phase prompt: asks for JSON array but provides `fileList` from `WorkspaceFileList` which only reads from current `.`, not repo root; `.go` source files missing from file list passed to LLM
- Client: `pkg/llm/client.go` rebuilt URL incorrectly for Google endpoint; message handling only used `messages[0]`; missing roles; no `systemInstruction` support; no `generationConfig`; no retry/backoff
- LLM empty outputs for Plan/Apply after tool declarations added (possible: model expects tool call invocation rather than text output when `tools` array present in payload but prompt doesn't instruct tool use clearly)

## Structural Design Gaps
- Pipeline (`pkg/cli/pipeline.go`, `pkg/pipeline/fsm.go`) calls phases sequentially without agent/tool registry integration
- Agent packages (`agents/*`) exist but pipeline never calls them; `codingagent/tools` not wired to `apply` (fixed in commit `7647b9d` but design remains fragile)
- No state transition machine documented (FSM exists but no abstract spec); phases hardwired to Go types
- `WorkspaceFileList` uses `.` directory instead of repo workspace root; excludes `.go` files when working directory isn't repo root
- `WorkspaceSnippet` exists but never called by pipeline; LLM never gets file content snippets, only file names
- No structured edit format enforcement; `llm/parse.go` uses regex instead of JSON parser; mismatched key names (`file_path` vs `filePath`)
- No retry mechanism for HTTP 503 / model unavailable; timeout only is 30s
- Tool declaration format (Google `function_declarations`) inserted incorrectly (nested interface literal errors); missing `systemInstruction` for some paths; missing content construction for all message roles
- No visibility/log mechanism before fix (added `LLM RAW` prints afterward); no persistent agent/tool invocation log until `TOOL_CALL_LOG.md` created manually

## Requirement Gaps Not Met
- `Record` phase (`phases/record/record.go`) present but pipeline integration unverified; `state.json` format exists but pipeline doesn't call it after publish/dry-run explicitly in `fsm` or `cli`
- `Audit` (`pkg/agent/audit`) isn't wired to `Review` or `Record` fully; `telemetryagent` has tools but no invocation in pipeline
- Domain/repo-level `build_cmd`/`test_cmd` from `resolv.yml` loaded but `phases/build/build.go` uses hardcoded `go build ./...` or `doBuildTest` without reading domain config properly
- `Plan` saves to `session.Plan` but `Apply` loads it; `Plan` does not read workspace file content; `Analyze` reads issue but not workspace snippets

## Redesign Requirement (language-independent)
- Separate LLM interface (transport + tool declarations) from pipeline orchestration (FSM states + transitions)
- Define abstract agent/tool registry (names + capabilities) independently of Go types
- Define workspace context interface independently of `os.ReadDir` path logic
- Define audit/state format (JSON/JSONL) independently of file path
- Define failure routing (loop back rules) independently of Go function calls
- Define edit format (structured JSON with file, old, new) independently of regex parsing
