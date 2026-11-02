Module 1: LLM Client & Prompt Gateway (pkg/llm/)

Scope:
- Single endpoint: OpenAI-compatible /v1/chat/completions
- Load credentials from credentials.json (env:VAR resolution via pkg/credentials/resolver)
- Structured JSON mode for LLM responses (edit blocks)
- Prompt templates for each Execution Stage agent (Analyze/Plan/Apply/Review/Publish)
- Budget awareness: token counting / cap enforcement (uses ExecutionConfig token cap)
- No framework; stdlib net/http + encoding/json only

Design inputs:
- Config: model endpoint + provider from domain/repo config (or global)
- Credentials: resolves <source>.default / <domain>.<source>.default via Resolver.ResolveValue (env: prefix)
- Output: parsed edit instructions (kind, filePath, oldText, newText) or structured JSON

Deliverable:
- pkg/llm/client.go (HTTP wrapper)
- pkg/llm/prompt.go (stage templates: Analyze, Plan, Apply, Review)
- pkg/llm/parse.go (structured edit extraction from JSON response)

No DB, no cgo, ≤2 new direct deps (none needed beyond existing yaml/cobra; pure stdlib HTTP)
