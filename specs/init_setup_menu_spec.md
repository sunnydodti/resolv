# Resolv Init & Setup Menu Specification

## Input Convention (ALL inputs)
Every input accepts: **raw value** OR **env:VARNAME**.
- Raw value: stored as-is, used directly
- `env:VARNAME`: stored as env reference, resolved from environment at runtime
- Sensitive values stored in `credentials.json` with `key`, `value` (raw), `env_ref`, `resolved_value` (runtime)

## Boolean Prompts (standardized)
Format: `[?] <message> [y/N] (default: N):` or `[y/N] (default: Y):`
- Same line, no extra vertical space
- Enter selects default

## Required Options with `[default]`
Format: `[?] Choice [1-4] (default: 1):`
- Enter selects default
- User can type different value

---

## `resolv init` — Global (one-time)

```
[I] Initializing Resolv globally...
[I] Every input: raw value or env:VARNAME

[?] Default LLM Provider:
    1. google      (gemini/gemini-2.5-flash) [default]
    2. anthropic   (claude-3-5-sonnet)
    3. openrouter  (deepseek/deepseek-r1)
    4. local       (ollama/gemma-4)
[?] Choice [1-4] (default: 1):

[?] Enable Langfuse telemetry? [y/N] (default: N):
[If Yes:]
    [?] Langfuse host URL [http://localhost:3000]:
    [?] Public key env var name [LANGFUSE_PUBLIC_KEY]:
    [?] Secret key env var name [LANGFUSE_SECRET_KEY]:

[?] Configure provider 'google'? [Y/n] (default: Y):
[If Yes:]
    [?] Model for google [gemini/gemini-2.5-flash]:
    [?] API key env var for google [GOOGLE_API_KEY]:
    [?] API base URL for google (optional):
[Repeat for anthropic, openrouter, local]

[S] Created config/resolv.yaml
[S] Resolv initialized globally.
```

## `resolv setup --project <name>` — Per-Project

```
[I] Setting up project: <name>
[I] Every input: raw value or env:VARNAME

[?] Repository source (e.g., github.com/org/repo):       REQUIRED
[?] Local repository path [./workspaces/<name>]:
[?] Credential key (e.g., GITHUB_TOKEN) [GITHUB_TOKEN]:
[?] Build command (optional):
[?] Test command (optional):
[?] Lint command (optional):

[?] Add reference repositories? [y/N] (default: N):
[If Yes:]
    [?] How many reference repos? (default: 1):
    [For each:]
        [?]   Source:
        [?]   Local path:
        [?]   Credential key [GITHUB_TOKEN]:

[?] Configure database schema source? [y/N] (default: N):
[If Yes:]
    [?]   Schema source:
    [?]   Migrations path (optional):

[?] Token Mappings — one per unique credential key:
[For each key:]
    [?]   <KEY> (raw value or env:VARNAME):

[S] Created config/projects/<name>.yaml
[S] Credentials saved to .resolv/sessions/<name>/setup/credentials.json
```

## What is NOT asked
- Project description (useless)
- Duplicate token prompts (each key asked once)
- Other data sources (add later via YAML edit)

## Re-running init/setup
- Previously set values shown as defaults in brackets
- Enter keeps previous value
- Type new value to change
- Only change what you need

---

**Approval required before implementation.**
