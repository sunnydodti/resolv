# Spec 1: CLI Foundation
- Goal: Setup basic CLI structure using `click` or `argparse`.
- Tasks:
    - Define entry point `resolv`.
    - Implement base command and flags (`--project`, `--verbose`, etc.).
    - Setup dependency management (`pyproject.toml`).

# Spec 2: Logging Facade
- Goal: Implement the `ResolvLogger` as defined in `plan/logger.md`.
- Tasks:
    - Create `core/logger.py`.
    - Implement tag-based coloring (ANSI TrueColor).
    - Setup file writing to `.resolv/sessions/.../audit.log` (stripping ANSI).
    - Ensure all output modules use the facade.

# Spec 3: Project Configuration & Setup
- Goal: Implement configuration loading.
- Tasks:
    - Setup Pydantic models for `resolv/config.yaml` and `resolv/projects/*.yaml`.
    - Implement `ConfigManager` to load global settings and project specific settings.
    - Validate environment variables (GitHub Token, OpenRouter API Key).

# Spec 4: Initialization & Workspace
- Goal: Stage 0 Implementation.
- Tasks:
    - Implement `GitAgent`.
    - Create `.resolv/sessions/` directory structure.
    - Implement session metadata initialization (JSON persistence).

# Spec 5: Agent Framework
- Goal: LangGraph & Agent integration.
- Tasks:
    - Integrate `LiteLLM` for OpenRouter routing.
    - Define `ContextState` Pydantic model for LangGraph.
    - Setup the 7-stage state machine scaffold.
    - Connect `CodingAgent` to `git` worktree operations.
