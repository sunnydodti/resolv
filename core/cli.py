"""
Resolv CLI Entry Point.
Single entry point with operational control flags and provider selection menu.
All output passes through ResolvLogger facade. Direct print statements are prohibited.
FAIL EARLY: No fallbacks, no defaults, no auto-selection. If anything is missing, fail at startup.
"""
import click
import os
import re
import uuid
import json
import yaml
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict

from core.logger import ResolvLogger, COLORS
from config.models import (
    load_global_config, load_project_config, ProjectConfig, CredentialsStore,
    get_global_config_path, get_project_config_path, get_resolv_dir,
    resolve_config_value, is_secret_field, _migrate_config_dict, save_credentials,
    load_credentials,
)
from core.graph import build_graph, load_state_from_checkpoint
from agents.tools.credentials import CredentialsSubAgent


# =============================================================================
# Helper: Prompt user through logger facade
# =============================================================================
def _prompt(logger: ResolvLogger, message: str, default: Optional[str] = None) -> str:
    """Prompt user for input through the logger facade. Returns stripped input."""
    if default:
        logger.prompt(f"{message} [{default}]: ")
    else:
        logger.prompt(f"{message}: ")
    val = input("").strip()
    if not val and default:
        return default
    return val


def _prompt_yes_no(logger: ResolvLogger, message: str, default: bool = True) -> bool:
    """Prompt user for yes/no through the logger facade. Returns boolean."""
    default_str = "Y/n" if default else "y/N"
    logger.prompt(f"{message} [{default_str}]: ")
    val = input("").strip().lower()
    if not val:
        return default
    return val in ("y", "yes")


def parse_repo_source(source: str) -> tuple[str, str]:
    """Parse a repo source into (base_host, path_after_host).

    Accepts:
      - https://github.com/org/repo
      - github.com/org/repo
      - git@github.com:org/repo.git
    Returns (base, path). If no path is present, path is "".
    """
    s = (source or "").strip()
    if not s:
        return "", ""
    # Strip protocol
    if "://" in s:
        s = s.split("://", 1)[1]
    # Handle scp-like syntax: git@host:path
    if "@" in s and ":" in s:
        after_at = s.split("@", 1)[1]
        if ":" in after_at:
            base, _, path = after_at.partition(":")
            return base, path
        return after_at, ""
    # Plain host/path
    if "/" in s:
        base, _, path = s.partition("/")
        return base, path
    return s, ""


def infer_source_from_base(base: str) -> str:
    """Infer the platform source short name from a base host.

    github.com -> github
    gitlab.com -> gitlab
    bitbucket.org -> bitbucket
    anything else -> custom
    """
    b = (base or "").lower().strip()
    if b == "github.com":
        return "github"
    if b == "gitlab.com":
        return "gitlab"
    if b == "bitbucket.org":
        return "bitbucket"
    return "custom"


def _yaml_str(value: Optional[str]) -> str:
    """Quote a value for YAML output so PyYAML reads it as a plain string
    literal. Single-quoted scalars treat backslash as literal (use these for
    Windows paths); double-quoted scalars treat backslash as an escape
    (use these for colons/slashes like URLs and env:/cred: prefixes)."""
    if value is None:
        return '""'
    s = str(value)
    needs_quote = any(c in s for c in (":", "\\", "/")) or s.strip() != s
    if not needs_quote:
        return s
    if "\\" in s:
        # Single-quoted: backslash is literal; escape ' by doubling.
        return "'" + s.replace("'", "''") + "'"
    # Double-quoted: escape backslash and double-quote.
    escaped = s.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def store_secret(store: CredentialsStore, config_key: str, value: str,
                 store_key: str) -> str:
    """If the field is a secret (by intent), move the value into the
    credential store and return a cred: prefix referencing it.
    Non-secret values are returned unchanged."""
    if not value:
        return value
    if is_secret_field(config_key):
        store.add(key=store_key, value=value)
        return f"cred:{store_key}"
    return value


def _display_value(value: Optional[str], cred_store: CredentialsStore) -> str:
    """Resolve cred:KEY references back to the stored value for user display.

    Users never input cred: prefixes — they input raw values or env:VARNAME.
    On re-runs, config.yaml stores cred:<key> internally, but we show the
    underlying stored value (e.g. env:LANGFUSE_PUBLIC_KEY) so the user sees
    what they originally entered."""
    if not value or not isinstance(value, str) or not value.startswith("cred:"):
        return value
    key = value[5:]
    raw = cred_store.get_raw(key)
    return raw if raw else value


# =============================================================================
# Project Discovery (read-only, no auto-selection)
# =============================================================================
def discover_projects() -> List[str]:
    """List available project configs from ~/.resolv/projects/. No auto-selection."""
    projects_dir = get_resolv_dir() / "projects"
    if not projects_dir.exists():
        return []
    projects = []
    for f in projects_dir.glob("*.yaml"):
        projects.append(f.stem)
    return sorted(projects)


def validate_project_exists(project_name: str) -> bool:
    """Check if a project config file exists."""
    return get_project_config_path(project_name).exists()


# =============================================================================
# Issue Reference Validation
# =============================================================================
def validate_issue_reference(ref: str) -> bool:
    """Validate that the issue reference looks like a valid issue identifier."""
    if not ref or len(ref.strip()) == 0:
        return False
    ref = ref.strip()
    if ref.startswith("http://") or ref.startswith("https://"):
        return "/issues/" in ref or "/pull/" in ref
    if ref.startswith("#"):
        return len(ref) > 1 and ref[1:].isdigit()
    if ref.isdigit():
        return True
    if "-" in ref and any(c.isdigit() for c in ref):
        return True
    return True


# =============================================================================
# Main CLI Group - No config loading here (each command handles its own)
# =============================================================================
@click.group()
@click.option('--project', help='Target project configuration')
@click.option('--verbose', is_flag=True, help='Enable verbose output')
@click.pass_context
def main(ctx, project, verbose):
    """Resolv: Autonomous Issue-to-PR CLI Agent"""
    # Log file is created per-session in cli.run once session_path is known.
    # Here we set up a base logger; run() will re-create with log_file.
    logger = ResolvLogger(verbose=verbose)
    ctx.obj = logger

    # Store project name if provided (loaded lazily by commands that need it)
    if project:
        ctx.obj._project_name = project
    else:
        ctx.obj._project_name = None
    ctx.obj._global_config = None
    ctx.obj._project_config = None

    # Store project name if provided (loaded lazily by commands that need it)
    if project:
        ctx.obj._project_name = project
    else:
        ctx.obj._project_name = None
    ctx.obj._global_config = None
    ctx.obj._project_config = None


# =============================================================================
# Run Command
# =============================================================================
@main.command()
@click.argument('issue_reference', required=True)
@click.option('--project', help='Target project configuration (overrides --project on main group)')
@click.option('--provider', help='LLM provider (overrides default from config)')
@click.option('--analysis', is_flag=True, help='Halt after Stage 2 (Plan), exit code 0')
@click.option('--resume', is_flag=True, help='Resume from last recorded stage')
@click.option('--dry-run', is_flag=True, help='Run through Stage 5, skip Stage 6 (Publish)')
@click.option('--verbose', is_flag=True, help='Enable verbose output')
@click.option('--max-healing-turns', type=int, required=False, default=3, help='Max self-healing turns')
@click.pass_context
def run(ctx, issue_reference, project, provider, analysis, resume, dry_run, verbose, max_healing_turns):
    """Run Resolv on an issue reference"""
    logger: ResolvLogger = ctx.obj

    # Validate issue reference
    if not validate_issue_reference(issue_reference):
        logger.error(f"Invalid issue reference: '{issue_reference}'")
        logger.info("Expected formats: https://github.com/org/repo/issues/123, #123, 123, PROJ-123")
        ctx.exit(1)

    # Load global config (fail fast)
    try:
        global_config = load_global_config()
        logger.info(f"Loaded global config: {global_config.default_provider}")
    except Exception as e:
        logger.error(f"Failed to load global config: {e}")
        ctx.exit(1)

    ctx.obj._global_config = global_config

    # Resolve project name: --project flag > main group --project > required
    project_name = project or ctx.obj._project_name
    if not project_name:
        logger.error("--project is required. Use --project <name>.")
        available = discover_projects()
        if available:
            logger.info(f"Available projects: {', '.join(available)}")
        ctx.exit(1)

    # Load project config (fail fast)
    try:
        project_config = load_project_config(project_name)
        logger.success(f"Project config loaded: {project_config.name}")
    except Exception as e:
        logger.error(f"Failed to load project config '{project_name}': {e}")
        ctx.exit(1)

    ctx.obj._project_config = project_config

    # Provider selection: --provider CLI option overrides default from config
    if provider:
        selected_provider = provider
        logger.info(f"LLM provider specified via --provider: {selected_provider}")
    elif global_config:
        selected_provider = global_config.default_provider
        available = list(global_config.providers.keys())
        logger.info(f"LLM provider from config default: {selected_provider}")
        logger.info(f"Available providers: {', '.join(available)}")
        logger.info("Override with: --provider <name>")
    else:
        logger.error("Global config not loaded. Cannot determine available providers.")
        ctx.exit(1)

    # Credential resolution (FAIL EARLY if missing)
    creds = resolve_credentials(logger, project_config)

    # Pre-flight: resolve all provider API keys and telemetry keys
    # Fail early if any cred:/env: reference cannot be resolved
    try:
        for prov_name, prov_cfg in global_config.providers.items():
            resolved = resolve_config_value(prov_cfg.api_key, creds)
            if not resolved:
                raise ValueError(f"empty resolved api key for {prov_name}")
            logger.debug(f"API key resolved for provider: {prov_name}")
        if global_config.telemetry.host:
            resolve_config_value(global_config.telemetry.host, creds)
        if global_config.telemetry.public_key:
            resolve_config_value(global_config.telemetry.public_key, creds)
        if global_config.telemetry.secret_key:
            resolve_config_value(global_config.telemetry.secret_key, creds)
    except ValueError as e:
        logger.error(f"Credential resolution failed: {e}")
        logger.info("Set the required env vars and re-run 'resolv setup --project <name>'")
        ctx.exit(1)

    # Extract issue ID from reference
    issue_id = issue_reference.split('/')[-1] if '/' in issue_reference else issue_reference
    if issue_id.startswith("#"):
        issue_id = issue_id[1:]

    # Build session path
    session_path = f".resolv/sessions/{project_name}/{issue_id}"
    Path(session_path).mkdir(parents=True, exist_ok=True)

    # Set up per-session log file for silent debug review
    log_file = str(Path(session_path) / "resolv.log")
    # Re-create logger with log_file so all levels (incl. debug) are captured to disk
    logger = ResolvLogger(verbose=verbose, log_file=log_file)
    ctx.obj = logger
    logger.debug(f"Log file: {log_file}")
    logger.debug(f"Verbose mode: {verbose}")

    # Handle resume
    initial_state = None
    if resume:
        from core.graph import load_state_from_checkpoint
        saved = load_state_from_checkpoint(session_path)
        if saved:
            logger.info(f"Resuming from stage: {saved.get('current_stage', 'unknown')}")
            initial_state = saved
        else:
            logger.error(f"No checkpoint found at {session_path}/metadata.json")
            ctx.exit(1)

    # Build initial state
    if not initial_state:
        initial_state = {
            "session_id": str(uuid.uuid4()),
            "issue_reference": issue_reference,
            "issue_id": issue_id,
            "project_name": project_name,
            "session_path": session_path,
            "log_file": log_file,
            "current_stage": "STAGE_0_SETUP",
            "status": "IN_PROGRESS",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "global_config": global_config.model_dump() if hasattr(global_config, 'model_dump') else dict(global_config),
            "project_config": project_config.model_dump() if hasattr(project_config, 'model_dump') else dict(project_config),
            "credentials": creds.model_dump() if hasattr(creds, 'model_dump') else creds,
            "selected_provider": selected_provider,
            "selected_model": None,
            "verbose": verbose,
            "context_data": None,
            "plan_data": None,
            "worktree_path": None,
            "modified_files": [],
            "diff_output": None,
            "test_results": None,
            "error_trace": None,
            "healing_turns": 0,
            "max_healing_turns": max_healing_turns,
            "security_result": None,
            "review_result": None,
            "pr_url": None,
            "pr_draft": False,
            "branch_name": None,
            "audit_log_path": None,
            "langfuse_trace_id": None,
            "token_usage": None,
            "cost_estimate": None,
        }

    # Override timestamps
    initial_state["session_id"] = str(uuid.uuid4())
    initial_state["created_at"] = datetime.now(timezone.utc).isoformat()
    initial_state["updated_at"] = initial_state["created_at"]

    # Build and run the graph
    try:
        graph = build_graph()
        logger.info(f"Starting Resolv pipeline for issue: {issue_reference}")

        session_id = str(uuid.uuid4())
        initial_state["session_id"] = session_id
        graph_config = {"configurable": {"thread_id": session_id}}

        final_state = None
        for event in graph.stream(initial_state, stream_mode="values", config=graph_config):
            final_state = event
            current_stage = event.get("current_stage", "unknown")
            logger.info(f"Stage progress: {current_stage}")

            if analysis and current_stage == "STAGE_2_PLAN":
                logger.info("--analysis flag set. Halting after Stage 2 (Plan).")
                logger.success("Analysis complete. Exiting cleanly (exit code 0).")
                ctx.exit(0)

        if final_state:
            logger.success(f"Pipeline completed. Final stage: {final_state.get('current_stage')}")
            if final_state.get("pr_url"):
                logger.success(f"Pull Request: {final_state['pr_url']}")
    except SystemExit:
        raise
    except Exception as e:
        import traceback
        logger.error(f"Pipeline failed: {e}")
        traceback.print_exc()
        ctx.exit(1)


# =============================================================================
# Credential Resolution (FAIL EARLY if missing)
# =============================================================================
def resolve_credentials(logger: ResolvLogger, project_config) -> CredentialsStore:
    """
    Load the global credential store (secrets collected during init/setup).
    Credentials are referenced as cred:<key> from config.yaml and resolved
    at runtime from credential.json (which may itself contain env:VAR refs).
    """
    cred_path = get_resolv_dir() / "credentials.json"
    if not cred_path.exists():
        logger.warning(
            "No global credential store found. Run 'resolv init' to set up credentials."
        )
        return CredentialsStore()
    store = load_credentials(str(cred_path))
    logger.success(f"Loaded {len(store.credentials)} credentials from global store")
    return store


# =============================================================================
# Init Command -- Global Resolv Initialization (No --project required)
# =============================================================================
@main.command()
@click.option('--verbose', is_flag=True, help='Enable verbose output')
@click.pass_context
def init(ctx, verbose):
    """Initialize Resolv globally (one-time setup). Prompts for global config at each step."""
    logger: ResolvLogger = ctx.obj

    logger.info("Initializing Resolv globally...")

    # Idempotent: load existing config as defaults if re-running
    resolv_config_path = get_global_config_path()
    existing_config = None
    if resolv_config_path.exists():
        try:
            with open(resolv_config_path, 'r') as f:
                existing_config = yaml.safe_load(f)
            existing_config = _migrate_config_dict(existing_config)
            logger.info(f"Existing global config found at {resolv_config_path}. Press Enter to keep current values.")
        except Exception as e:
            logger.warning(f"Could not read existing config: {e}. Starting fresh.")

    # Create directory structure
    dirs = [
        str(get_resolv_dir() / "projects"),
        "agents/tools",
        "core",
        ".resolv",
    ]
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)
        logger.debug(f"Created directory: {d}/")

    logger.info("=== Resolv Global Initialization ===")
    logger.info("  Every input: raw value or env:VARNAME")
    logger.info("  Press Enter to accept defaults shown in brackets.")

    # Global credential store, auto-managed by Resolv (user never edits it).
    # Secrets collected by intent are stored here and referenced as cred:<key>
    # from config.yaml so secrets never live in config.yaml.
    cred_store = CredentialsStore()
    # Load existing credentials so we can display original user values (env:VARNAME)
    # on re-runs instead of the internal cred:<key> references.
    existing_cred_path = get_resolv_dir() / "credentials.json"
    if existing_cred_path.exists():
        try:
            existing_store = load_credentials(str(existing_cred_path))
            for key, entry in existing_store.credentials.items():
                cred_store.add(key=key, value=entry.value, env_ref=entry.env_ref)
        except Exception as e:
            logger.warning(f"Could not load existing credentials: {e}")

    # --- Stage 1: Default Provider ---
    logger.info("Step 1: Default LLM Provider")
    default_provider_val = existing_config.get("default_provider", "google") if existing_config else "google"
    default_marker = " [default]"
    providers_list = [
        (1, "google", "gemini/gemini-2.5-flash"),
        (2, "anthropic", "claude-3-5-sonnet"),
        (3, "openrouter", "deepseek/deepseek-r1"),
        (4, "local", "ollama/gemma-4"),
    ]
    for num, name, model_str in providers_list:
        marker = default_marker if name == default_provider_val else ""
        logger.info(f"    {num}. {name:15s} ({model_str}){marker}")
    logger.prompt(f"Choice [1-4] (default: {default_provider_val}): ")
    provider_choice = input("").strip() or "1"
    provider_map = {"1": "google", "2": "anthropic", "3": "openrouter", "4": "local"}
    default_provider = provider_map.get(provider_choice, provider_choice if provider_choice in provider_map.values() else "google")

    # --- Step 2: Telemetry ---
    logger.info("Step 2: Telemetry (Langfuse)")
    telemetry_enabled = _prompt_yes_no(logger, "Enable Langfuse telemetry?", default=True)

    langfuse_host_default = _display_value(
        existing_config.get("telemetry", {}).get("host", "http://localhost:3000") if existing_config else "http://localhost:3000", cred_store)
    langfuse_public_key_default = _display_value(
        existing_config.get("telemetry", {}).get("public_key", "env:LANGFUSE_PUBLIC_KEY") if existing_config else "env:LANGFUSE_PUBLIC_KEY", cred_store)
    langfuse_secret_key_default = _display_value(
        existing_config.get("telemetry", {}).get("secret_key", "env:LANGFUSE_SECRET_KEY") if existing_config else "env:LANGFUSE_SECRET_KEY", cred_store)

    langfuse_host = "http://localhost:3000"
    langfuse_public_key = "env:LANGFUSE_PUBLIC_KEY"
    langfuse_secret_key = "env:LANGFUSE_SECRET_KEY"

    if telemetry_enabled:
        langfuse_host = _prompt(logger, "Langfuse host URL (raw value or env:VARNAME)", default=langfuse_host_default)
        langfuse_public_key = _prompt(logger, "Public key (raw value or env:VARNAME)", default=langfuse_public_key_default)
        langfuse_secret_key = _prompt(logger, "Secret key (raw value or env:VARNAME)", default=langfuse_secret_key_default)

        # Secrets are stored in the credential store, referenced as cred:<key>
        langfuse_public_key = store_secret(cred_store, "public_key", langfuse_public_key, "langfuse_public_key")
        langfuse_secret_key = store_secret(cred_store, "secret_key", langfuse_secret_key, "langfuse_secret_key")

    # --- Step 3: Clone Root Directory ---
    logger.info("Step 3: Clone Root Directory")
    clone_root_default = existing_config.get("clone_root", str(get_resolv_dir() / "workspaces")) if existing_config else str(get_resolv_dir() / "workspaces")
    clone_root = _prompt(logger, "Clone root directory (raw value or env:VARNAME)", default=clone_root_default)
    if not clone_root:
        clone_root = str(get_resolv_dir() / "workspaces")

    # --- Step 4: Providers ---
    logger.info("Step 4: Configure LLM Providers")
    existing_providers = existing_config.get("providers", {}) if existing_config else {}
    providers = {}
    for prov_name in ["google", "anthropic", "openrouter", "local"]:
        existing_prov = existing_providers.get(prov_name, {})
        default_add = bool(existing_prov)
        add = _prompt_yes_no(logger, f"Configure provider '{prov_name}'?", default=default_add)
        if not add:
            continue
        model_defaults = {
            "google": "gemini/gemini-2.5-flash",
            "anthropic": "anthropic/claude-3-5-sonnet",
            "openrouter": "openrouter/deepseek/deepseek-r1",
            "local": "ollama/gemma-4",
        }
        model_default = existing_prov.get("model", model_defaults.get(prov_name, "")) if existing_prov else model_defaults.get(prov_name, "")
        model = _prompt(logger, f"  Model for {prov_name} (raw value or env:VARNAME)", default=model_default)
        api_key_default = _display_value(
            existing_prov.get("api_key", f"env:{prov_name.upper()}_API_KEY") if existing_prov else f"env:{prov_name.upper()}_API_KEY", cred_store)
        api_key = _prompt(logger, f"  API key for {prov_name} (raw value or env:VARNAME)", default=api_key_default)
        api_base_default = existing_prov.get("api_base", "") if existing_prov else ""
        api_base = _prompt(logger, f"  API base URL for {prov_name} (optional, raw value or env:VARNAME)", default=api_base_default)

        # api_key is a secret -> stored in credential store as cred:<store_key>
        api_key = store_secret(cred_store, "api_key", api_key, f"{prov_name}_api_key")

        providers[prov_name] = {
            "model": model,
            "api_key": api_key,
        }
        if api_base:
            providers[prov_name]["api_base"] = api_base

    if not providers:
        logger.error("At least one provider must be configured.")
        ctx.exit(1)

    # Build global config YAML (all inputs collected -- write atomically at end)
    telemetry_enabled_str = str(telemetry_enabled).lower()
    telemetry_section = f"""  enabled: {telemetry_enabled_str}
  platform: langfuse
  host: {_yaml_str(langfuse_host)}
  public_key: {_yaml_str(langfuse_public_key)}
  secret_key: {_yaml_str(langfuse_secret_key)}"""

    providers_section = ""
    for prov_name, prov_cfg in providers.items():
        providers_section += f"  {prov_name}:\n"
        providers_section += f"    model: {_yaml_str(prov_cfg['model'])}\n"
        providers_section += f"    api_key: {_yaml_str(prov_cfg['api_key'])}\n"
        if prov_cfg.get("api_base"):
            providers_section += f"    api_base: {_yaml_str(prov_cfg['api_base'])}\n"

    global_config_yaml = f"""default_provider: {_yaml_str(default_provider)}
telemetry:
{telemetry_section}
clone_root: {_yaml_str(clone_root)}
providers:
{providers_section}"""

    # Write config atomically (only now are files on disk updated)
    resolv_config_path.write_text(global_config_yaml)
    logger.success(f"Created {resolv_config_path}")

    # Persist the credential store (secrets never live in config.yaml)
    cred_path = get_resolv_dir() / "credentials.json"
    save_credentials(str(cred_path), cred_store)
    logger.success(f"Created {cred_path} (secrets stored here, referenced as cred: from config.yaml)")

    # Create .gitignore if missing
    gitignore = Path(".gitignore")
    if not gitignore.exists():
        gitignore.write_text("""# Resolv
.resolv/
__pycache__/
*.pyc
.env
.venv/
.pytest_cache/
.langfuse/
.python-version
.idea/
.vscode/
dist/
build/
*.egg-info/
""")
        logger.success("Created .gitignore")

    logger.success("Resolv initialized globally.")
    logger.info("Next: run 'resolv setup --project <name>' to configure a project.")


# =============================================================================
# Setup Command -- Per-Project Setup (--project required)
# =============================================================================
@main.command()
@click.option('--project', required=True, help='Target project configuration name')
@click.option('--verbose', is_flag=True, help='Enable verbose output')
@click.pass_context
def setup(ctx, project, verbose):
    """Set up a project for Resolv (per-project configuration). Prompts for repo, credentials, and workspace at each step."""
    logger: ResolvLogger = ctx.obj

    logger.info(f"Setting up project: {project}")

    # FAIL EARLY: Global config must exist
    resolv_config = get_global_config_path()
    if not resolv_config.exists():
        logger.error("Resolv not initialized globally. Run 'resolv init' first.")
        ctx.exit(1)

    # Load global config for provider list (if needed later)
    try:
        global_config = load_global_config()
        ctx.obj._global_config = global_config
    except Exception as e:
        logger.error(f"Failed to load global config: {e}")
        ctx.exit(1)

    clone_root = getattr(global_config, 'clone_root', str(get_resolv_dir() / "workspaces"))

    # Load existing project config as defaults if re-running
    project_config_path = get_project_config_path(project)
    existing_project = None
    if project_config_path.exists():
        try:
            import yaml
            with open(project_config_path, 'r') as f:
                existing_project = yaml.safe_load(f)
            logger.info(f"Existing project config found at {project_config_path}. Press Enter to keep current values.")
        except Exception as e:
            logger.warning(f"Could not read existing config: {e}. Starting fresh.")

    # Create projects directory if missing
    project_config_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"=== Project Setup: {project} ===")
    logger.info("  Every input: raw value or env:VARNAME")
    logger.info("  Press Enter to accept defaults shown in brackets.")

    # --- Step 1: Primary Repository ---
    existing_repo = existing_project.get("repos", {}).get("primary", {}) if existing_project else {}
    existing_source = existing_repo.get("source", "") if existing_repo else ""
    existing_base = existing_repo.get("base", "") if existing_repo else ""
    existing_path = existing_repo.get("path", "") if existing_repo else ""

    logger.info("Step 1: Primary Repository")
    logger.info("  Specify the primary repository Resolv will work on.")

    # Source platform selection
    platforms = [
        (1, "github", "github.com"),
        (2, "gitlab", "gitlab.com"),
        (3, "bitbucket", "bitbucket.org"),
        (4, "custom", ""),
    ]
    platform_default_index = 1
    for i, (num, name, base) in enumerate(platforms):
        if name == existing_source:
            platform_default_index = num
            break
    for num, name, base in platforms:
        base_str = f" ({base})" if base else ""
        marker = " [default]" if num == platform_default_index else ""
        logger.info(f"    {num}. {name}{base_str}{marker}")
    logger.prompt(f"Source platform [1-4] (default: {platform_default_index}): ")
    platform_choice = input("").strip() or str(platform_default_index)
    platform_map = {"1": "github", "2": "gitlab", "3": "bitbucket", "4": "custom"}
    repo_source = platform_map.get(
        platform_choice,
        platform_choice if platform_choice in ("github", "gitlab", "bitbucket", "custom") else "github",
    )

    # Suggested base from selected platform (or existing)
    suggested_base = existing_base if existing_base else ""
    for num, name, base in platforms:
        if name == repo_source and base:
            suggested_base = base
            break

    # Ask for repository link — default to previously entered base/path if re-running
    if existing_base and existing_path:
        link_default = f"{existing_base}/{existing_path}"
    elif existing_source and not existing_source.startswith("env:"):
        link_default = existing_source
    else:
        link_default = ""
    repo_link = _prompt(logger, f"  Repository link (e.g. {suggested_base}/org/repo) (raw value or env:VARNAME)", default=link_default)
    if not repo_link:
        logger.error("Repository link is required.")
        ctx.exit(1)

    repo_base = ""
    repo_path_part = ""

    if repo_link.startswith("env:"):
        # Cannot parse an env reference now; ask base and path separately
        logger.info("  Link is an env reference — base and path must be entered manually.")
        repo_base = _prompt(logger, f"  Base host (e.g. {suggested_base})", default=suggested_base)
        repo_path_part = _prompt(logger, f"  Path (e.g. org/repo)", default=existing_path)
        if not repo_base:
            repo_base = suggested_base
    else:
        parsed_base, parsed_path = parse_repo_source(repo_link)
        if parsed_base and parsed_path:
            # Able to infer base and path from the link — display as defaults
            inferred_source = infer_source_from_base(parsed_base)
            logger.info(f"  Inferred source/platform: {inferred_source}")
            logger.info(f"  Inferred base host: {parsed_base}")
            logger.info(f"  Inferred path: {parsed_path}")
            repo_source = _prompt(logger, f"  Source/platform", default=inferred_source or repo_source)
            repo_base = _prompt(logger, f"  Base host", default=parsed_base or suggested_base)
            repo_path_part = _prompt(logger, f"  Path", default=parsed_path)
        else:
            # Not able to infer — ask for parts one by one with suggested defaults
            logger.info("  Could not infer base and path from the link; please enter them manually.")
            repo_base = _prompt(logger, f"  Base host (e.g. {suggested_base})", default=suggested_base)
            repo_path_part = _prompt(logger, f"  Path (e.g. org/repo)", default=existing_path)
            if not repo_base:
                repo_base = suggested_base

    if not repo_base or not repo_path_part:
        logger.error("Base host and path are required.")
        ctx.exit(1)

    # Auto-compute repopath as clone_root/<project>
    repo_path = str(Path(clone_root) / project)

    # Load existing credential store so we can show the previous credential as default
    credential_store = CredentialsStore()
    existing_cred_path = get_resolv_dir() / "credentials.json"
    if existing_cred_path.exists():
        try:
            existing_store = load_credentials(str(existing_cred_path))
            for key, entry in existing_store.credentials.items():
                credential_store.add(key=key, value=entry.value, env_ref=entry.env_ref)
        except Exception as e:
            logger.warning(f"Could not load existing credentials: {e}")

    # Prompt for credential value — show existing as default, specific message per source
    credential_key = f"{repo_source}_token"
    existing_cred_value = credential_store.get_raw(credential_key)
    cred_display = _display_value(existing_cred_value, credential_store) if existing_cred_value else ""
    cred_msg = f"  {repo_source} API key/token for {repo_base} (raw value or env:VARNAME)"
    credential_value = _prompt(logger, cred_msg, default=cred_display)
    if credential_value:
        credential_store.add(key=credential_key, value=credential_value)

    build_cmd = _prompt(logger, "Build command (optional) (raw value or env:VARNAME)", default="")
    test_cmd = _prompt(logger, "Test command (optional) (raw value or env:VARNAME)", default="")
    lint_cmd = _prompt(logger, "Lint command (optional) (raw value or env:VARNAME)", default="")

    # --- Step 2: Reference Repositories ---
    logger.info("Step 2: Reference Repositories")
    add_refs = _prompt_yes_no(logger, "Add reference repositories?", default=False)
    reference_repos = []
    if add_refs:
        num_refs_str = _prompt(logger, "How many reference repos?", default="1")
        try:
            num_refs = int(num_refs_str)
        except ValueError:
            num_refs = 1
        for i in range(num_refs):
            logger.info(f"  Reference Repo {i + 1}:")
            r_source = _prompt(logger, "    Repository source (e.g. github.com/org/repo) (raw value or env:VARNAME)")
            if r_source:
                if r_source.startswith("env:"):
                    r_base = ""
                    r_path_part = ""
                    r_source_platform = "custom"
                else:
                    r_base, r_path_part = parse_repo_source(r_source)
                    r_source_platform = infer_source_from_base(r_base)
                # Prompt for reference repo credential; stored in global credential store
                r_cred_val = _prompt(logger, f"    Credential value (raw value or env:VARNAME)")
                if r_cred_val:
                    credential_store.add(key=f"{r_source_platform}_token_ref_{i}", value=r_cred_val)
                reference_repos.append({
                    "source": r_source_platform,
                    "base": r_base,
                    "path": r_path_part,
                    "repopath": str(Path(clone_root) / f"ref_{i}"),
                })

    # --- Step 3: Database ---
    logger.info("Step 3: Database Configuration")
    add_db = _prompt_yes_no(logger, "Configure database schema source?", default=False)
    database_config = {}
    if add_db:
        schema_source = _prompt(logger, "  Schema source (e.g., postgresql://user:pass@localhost:5432/db) (raw value or env:VARNAME)")
        migrations_path = _prompt(logger, "  Migrations path (optional) (raw value or env:VARNAME)", default="")
        database_config = {
            "schema_source": schema_source if schema_source else None,
            "migrations_path": migrations_path if migrations_path else None,
        }

    # Build project config YAML (all inputs collected -- write atomically at end)
    # Quote Windows paths with backslashes - escape backslashes for YAML
    def yaml_quote(s: str) -> str:
        return f'"{s.replace(chr(92), chr(92)+chr(92))}"' if '\\' in s or ':' in s or '/' in s else s
    repo_source_quoted = yaml_quote(repo_source)
    repo_path_quoted = yaml_quote(repo_path)

    repo_entry = f"""  primary:
    source: {repo_source_quoted}
    base: {yaml_quote(repo_base) if repo_base else "null"}
    path: {yaml_quote(repo_path_part) if repo_path_part else "null"}
    repopath: {repo_path_quoted}"""
    if build_cmd:
        repo_entry += f"\n    buildcmd: {build_cmd}"
    if test_cmd:
        repo_entry += f"\n    testcmd: {test_cmd}"
    if lint_cmd:
        repo_entry += f"\n    lintcmd: {lint_cmd}"

    ref_section = "reference: []\n"
    if reference_repos:
        ref_section = "reference:\n"
        for r in reference_repos:
            r_source_quoted = yaml_quote(r["source"])
            r_base_quoted = yaml_quote(r.get("base", "")) if r.get("base") else "null"
            r_path_quoted = yaml_quote(r.get("path", "")) if r.get("path") else "null"
            r_repopath_quoted = yaml_quote(r["repopath"])
            ref_section += f"- source: {r_source_quoted}\n"
            ref_section += f"  base: {r_base_quoted}\n"
            ref_section += f"  path: {r_path_quoted}\n"
            ref_section += f"  repopath: {r_repopath_quoted}\n"

    data_section = "data: {}\n"
    if database_config:
        data_section = "data:\n  database:\n"
        ds = database_config.get("schema_source") or "null"
        mp = database_config.get("migrations_path") or "null"
        ds_quoted = yaml_quote(ds) if ds else "null"
        mp_quoted = yaml_quote(mp) if mp else "null"
        data_section += f"    schema_source: {ds_quoted}\n    migrations_path: {mp_quoted}\n"

    project_config_yaml = f"""name: {project}
repos:
{repo_entry}
{ref_section}{data_section}"""

    # Write atomically
    project_config_path.write_text(project_config_yaml)
    logger.success(f"Created {project_config_path}")

    # Resolve and store credentials in credentials.json
    session_path = f".resolv/sessions/{project}/setup"
    Path(session_path).mkdir(parents=True, exist_ok=True)

    # Save credentials to the global credential store (so `run` can resolve them).
    # Merge with any existing credentials so re-running setup doesn't lose them.
    cred_agent = CredentialsSubAgent(logger, None)
    global_cred_path = get_resolv_dir() / "credentials.json"
    if global_cred_path.exists():
        try:
            existing_store = load_credentials(str(global_cred_path))
            for key, entry in existing_store.credentials.items():
                if key not in credential_store.credentials:
                    credential_store.add(
                        key=key, value=entry.value, env_ref=entry.env_ref
                    )
        except Exception as e:
            logger.warning(f"Could not merge existing credentials: {e}")
    save_credentials(str(global_cred_path), credential_store)
    logger.success(f"Saved {len(credential_store.credentials)} credentials to {global_cred_path}")

    # Also persist a copy under the setup session for backward compatibility.
    session_path = f".resolv/sessions/{project}/setup"
    Path(session_path).mkdir(parents=True, exist_ok=True)
    cred_agent.save_to_session(session_path, credential_store)
    logger.success(f"Saved credentials to {session_path}/credentials.json")

    # Warn about any secret fields that still have no value (user must set env var later)
    missing = []
    for key in sorted(credential_store.credentials.keys()):
        raw = credential_store.get_raw(key)
        if not raw:
            missing.append(key)
    if missing:
        logger.warning("Some credentials have no value (set the env var before running):")
        for m in missing:
            logger.warning(f"  - {m}")
        logger.info("  Set them before running Resolv, e.g.:")
        if missing:
            logger.info(f"    $env:{missing[0]}=\"your-token\"  (Windows PowerShell)")
            logger.info(f"    export {missing[0]}=\"your-token\"  (Linux/macOS)")

    # Validate workspace paths
    if Path(repo_path).exists():
        logger.success(f"Repository path exists: {repo_path}")
    else:
        logger.warning(f"Repository path not found: {repo_path}")
        logger.info(f"Create it or update repopath in ~/.resolv/projects/{project}.yaml")

    logger.success(f"Project '{project}' set up successfully.")
    logger.info(f"Next: run 'resolv --project {project} --provider <name> run <issue_reference>'")


if __name__ == '__main__':
    main()