# Framework Options (Platform/Language Independent — Evaluated Nov 2026)

## Evaluation Criteria
- Language / runtime (Go vs Python vs TypeScript vs .NET)
- Orchestration style (graph/state-machine vs role-based vs pipeline vs handoff)
- Tool integration method (native function declarations / MCP / adapter)
- State / durability (checkpoint, durable execution, memory)
- Observability (tracing, audit log, evaluation)
- Vendor/model lock-in
- Production evidence / maturity
- Suitability for resolution pipeline (structured edits, git, build/test, audit)

## Option A: Google ADK (Python / GCP; Go SDK emerging)
- Pros: native Gemini, multimodal, A2A, hierarchical agents, pre-built tools
- Cons: Python-first; GCP lock-in; medium vendor coupling; docs maturing
- Fit: good if pipeline stays Python / GCP; not ideal for Go-only team

## Option B: LangGraph / LangChain (Python — graph/state-machine)
- Pros: explicit state graph, durable execution, human-in-loop, LangSmith tracing, production users (Klarna, Uber, JPMorgan); supports MCP; best for audit/review loops
- Cons: Python only; steep learning curve; over-engineered for simple edit-only pipeline
- Fit: best if redesign uses graph orchestration (Analyze→Plan→Apply→Review→Publish) with checkpoints; can embed from Go via subprocess/JSON

## Option C: Pydantic AI (Python — type-safe, durable, MCP-native)
- Pros: type-safe Python agents, native MCP/A2A, durable execution, minimal overhead, production trend; can define agents as YAML/JSON
- Cons: Python only; smaller ecosystem than LangGraph; newer
- Fit: best if team wants type-safe, low-abstraction agent design; good for structured edit pipelines

## Option D: OpenAI Agents SDK (Python / TS — handoff-based, lightweight)
- Pros: minimal primitives (agents, handoffs, guardrails, sessions, tracing); sandboxed tool use; 100+ LLMs
- Cons: handoff style not graph-based; less explicit state management; opinionated
- Fit: good if pipeline is linear with sub-agent delegation (e.g., context agent + coding agent)

## Option E: Custom minimal state-machine (any language — Go, Python, etc.)
- Pros: exact match to requirements; no framework dependency; full control over audit/state/types; can use existing Go code; can call Python framework via API if needed
- Cons: must build orchestration, retry, budget, observation, tool registry, failure routing
- Fit: best for current codebase (already has `pkg/pipeline/fsm.go`, agent packages, tool package); redesign around explicit state machine rather than framework

## Option F: Mastra (TypeScript — graph/workflows, edge)
- Pros: TypeScript-native; OpenTelemetry; workflow primitives
- Cons: TypeScript only; not Go; newer ecosystem
- Fit: only if team moves to TypeScript stack

## Option G: CrewAI / AutoGen / Microsoft Agent Framework
- Pros: multi-agent role-based; enterprise (AutoGen merged into Microsoft Agent Framework)
- Cons: Python; maintenance-mode AutoGen; role-based less suitable for structured edit pipeline
- Fit: not best for this pipeline

## Recommendation
For this pipeline (structured edit + audit + budget + exhaustion), the best design is not a framework choice but an architecture: **custom minimal state-machine in preferred language + standardized interfaces**. If team wants framework support without losing Go, embed LangGraph or Pydantic AI as a Python sidecar via HTTP/JSON, or use Go SDK (`agent-sdk-go`) for basic orchestration.

Preferred path (language-independent spec):
- Define FSM (states + transitions + budgets) abstractly
- Define agent/tool registry (names, inputs, outputs) abstractly
- Define LLM interface (transport + tool schema + retry) abstractly
- Implement in Go (current) OR embed Python framework via subprocess
- Keep `.resolv/` files (audit, state) language-independent
