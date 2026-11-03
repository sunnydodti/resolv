# Step 001: Project Foundation & CLI Scaffolding

## 1. Environment & Version Control
- **Git Initialization:**
    - Create `.gitignore` to exclude local state, virtual environments, and sensitive data.
- **Dependency Management:**
    - Initialize `pyproject.toml` (using Poetry or standard pip/setuptools).
    - Dependencies: `click` (CLI), `pydantic` (schemas), `langgraph` (FSM), `litellm` (LLM gateway), `instructor` (schema enforcement).

## 2. Directory Structure
```text
resolv/
├── .resolv/            # Session/Worktree storage (ignored)
├── core/
│   ├── __init__.py
│   ├── cli.py          # Entry point
│   └── logger.py       # Centralized logger facade
├── config/             # YAML schemas
├── agents/             # LangGraph nodes/agents
├── specs/              # Technical design specs
├── pyproject.toml
└── .gitignore
```

## 3. Implementation Details
### 3.1. `.gitignore`
- `.resolv/`
- `__pycache__/`
- `*.pyc`
- `.env`
- `.venv/`
- `.pytest_cache/`
- `.langfuse/`

### 3.2. Entry Point (`core/cli.py`)
- Implement `click.group` as the primary entry point.
- Implement command flags:
    - `--project`: STRING (required/default logic)
    - `--verbose`: FLAG (global debug enable)
    - `issue_reference`: ARG (positional)
- Setup basic argument parsing logic.

### 3.3. Initial Build
- Run `poetry install` (or equivalent).
- Verify entry point invocation: `resolv --help` displays command documentation.
