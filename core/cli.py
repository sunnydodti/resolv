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


def _yaml_str(value: Optional[str]) -> str:
    """Quote a value for YAML output if it contains characters that could
    be misinterpreted (colon, backslash, slash) so PyYAML reads it as a
    plain string literal. Returns the value wrapped in double quotes when
    needed, else the raw value."""
    if value is None:
        return '""'
    s = str(value)
    if any(c in s for c in (":", "\\", "/")) or s.strip() != s:
        escaped = s.replace('"', '\\"')
        return f'"{escaped}"'
    return s


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
    logger = ResolvLogger(verbose=verbose)
    ctx.obj = logger

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

    # Provider selection: --project flag > main group > no auto-selection
    if provider:
        selected_provider = provider
        logger.info(f"LLM provider specified via --provider: {selected_provider}")
    elif global_config:
        available = list(global_config.providers.keys())
        default_provider = global_config.default_provider
        logger.error("--provider is required. Specify an LLM provider.")
        logger.info(f"Available providers: {', '.join(available)}")
        logger.info(f"Default in config: {default_provider}")
        logger.info("Re-run with: resolv --project <name> --provider <name> <issue_reference>")
        ctx.exit(1)
    else:
        logger.error("Global config not loaded. Cannot determine available providers.")
        ctx.exit(1)

    # Credential resolution (FAIL EARLY if missing)
    creds = resolve_credentials(logger, project_config)

    # Extract issue ID from reference
    issue_id = issue_reference.split('/')[-1] if '/' in issue_reference else issue_reference
    if issue_id.startswith("#"):
        issue_id = issue_id[1:]

    # Build session path
    session_path = f".resolv/sessions/{project_name}/{issue_id}"

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
            "current_stage": "STAGE_0_SETUP",
            "status": "IN_PROGRESS",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "global_config": global_config.model_dump() if hasattr(global_config, 'model_dump') else dict(global_config),
            "project_config": project_config.model_dump() if hasattr(project_config, 'model_dump') else dict(project_config),
            "credentials": creds.model_dump() if hasattr(creds, 'model_dump') else creds,
            "selected_provider": selected_provider,
            "selected_model": None,
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
            "_logger": logger,
        }

    # Override timestamps
    initial_state["session_id"] = str(uuid.uuid4())
    initial_state["created_at"] = datetime.now(timezone.utc).isoformat()
    initial_state["updated_at"] = initial_state["created_at"]

    # Build and run the graph
    try:
        graph = build_graph()
        logger.info(f"Starting Resolv pipeline for issue: {issue_reference}")

        final_state = None
        for event in graph.stream(initial_state, stream_mode="values"):
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
        logger.error(f"Pipeline failed: {e}")
        if verbose:
            import traceback
            logger.debug(traceback.format_exc())
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

    def store_secret(config_key: str, value: str, store_key: str) -> str:
        """If the field is a secret (by intent), move the value into the
        credential store and return a cred: prefix referencing it.
        Non-secret values are returned unchanged."""
        if not value:
            return value
        if is_secret_field(config_key):
            cred_store.add(key=store_key, value=value)
            return f"cred:{store_key}"
        return value

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

    langfuse_host_default = existing_config.get("telemetry", {}).get("host", "http://localhost:3000") if existing_config else "http://localhost:3000"
    langfuse_public_key_default = existing_config.get("telemetry", {}).get("public_key", "env:LANGFUSE_PUBLIC_KEY") if existing_config else "env:LANGFUSE_PUBLIC_KEY"
    langfuse_secret_key_default = existing_config.get("telemetry", {}).get("secret_key", "env:LANGFUSE_SECRET_KEY") if existing_config else "env:LANGFUSE_SECRET_KEY"

    langfuse_host = "http://localhost:3000"
    langfuse_public_key = "env:LANGFUSE_PUBLIC_KEY"
    langfuse_secret_key = "env:LANGFUSE_SECRET_KEY"

    if telemetry_enabled:
        langfuse_host = _prompt(logger, "Langfuse host URL (raw value or env:VARNAME)", default=langfuse_host_default)
        langfuse_public_key = _prompt(logger, "Public key (raw value or env:VARNAME)", default=langfuse_public_key_default)
        langfuse_secret_key = _prompt(logger, "Secret key (raw value or env:VARNAME)", default=langfuse_secret_key_default)

        # Secrets are stored in the credential store, referenced as cred:<key>
        langfuse_public_key = store_secret("public_key", langfuse_public_key, "langfuse_public_key")
        langfuse_secret_key = store_secret("secret_key", langfuse_secret_key, "langfuse_secret_key")

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
        api_key_default = existing_prov.get("api_key", f"env:{prov_name.upper()}_API_KEY") if existing_prov else f"env:{prov_name.upper()}_API_KEY"
        api_key = _prompt(logger, f"  API key for {prov_name} (raw value or env:VARNAME)", default=api_key_default)
        api_base_default = existing_prov.get("api_base", "") if existing_prov else ""
        api_base = _prompt(logger, f"  API base URL for {prov_name} (optional, raw value or env:VARNAME)", default=api_base_default)

        # api_key is a secret -> stored in credential store as cred:<store_key>
        api_key = store_secret("api_key", api_key, f"{prov_name}_api_key")

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
    logger.info("Step 1: Primary Repository")
    existing_repo = existing_project.get("repos", {}).get("primary", {}) if existing_project else {}
    repo_source_default = existing_repo.get("source", "") if existing_repo else ""

    # Repository source selection (options + custom)
    logger.info("Step 1: Primary Repository")
    logger.info("    1. github.com")
    logger.info("    2. gitlab.com")
    logger.info("    3. bitbucket.org")
    logger.info("    4. Custom URL")
    logger.prompt(f"Choice [1-4] (default: 1): ")
    source_choice = input("").strip() or "1"
    source_map = {"1": "github.com", "2": "gitlab.com", "3": "bitbucket.org", "4": "custom"}
    source_choice = source_map.get(source_choice, "custom")

    if source_choice == "custom":
        repo_source = _prompt(logger, "Repository source URL (raw value or env:VARNAME)", default=repo_source_default)
        if not repo_source:
            logger.error("Repository source is required.")
            ctx.exit(1)
    else:
        repo_source = source_choice
        logger.info(f"  Repository source: {repo_source}")

    # Auto-compute repopath as clone_root/<project>
    repo_path = str(Path(clone_root) / project)

    # Derive credential key from repo source host
    existing_cred_key = existing_repo.get("credentialkey", "") if existing_repo else ""
    credential_key = existing_cred_key if existing_cred_key else ""
    if not credential_key:
        host_match = re.search(r'://([^/]+)/', repo_source)
        if host_match:
            host = host_match.group(1)
            host_key_map = {
                'github.com': 'GITHUB_TOKEN',
                'anthropic.com': 'GITLAB_TOKEN',
                'bitbucket.org': 'BITBUCKET_TOKEN',
            }
            credential_key = host_key_map.get(host, f"{host.replace('.', '_').upper()}_TOKEN")
        else:
            credential_key = "GITHUB_TOKEN"

    credential_value = _prompt(logger, f"  Credential value (raw value or env:VARNAME)")
    # Secrets (by intent: token/key/credential) are stored in the credential
    # store and referenced as cred:<key> from config.yaml — never raw in config.
    credential_store = CredentialsStore()
    credential_config_ref = ""  # what gets written into config.yaml for this secret
    if credential_value:
        credential_config_ref = store_secret("credentialkey", credential_value, credential_key)
        credential_store.add(key=credential_key, value=credential_value)
    token_mappings = {credential_key: credential_config_ref} if credential_config_ref else {}

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
            r_source = _prompt(logger, "    Source (e.g., github.com/org/repo) (raw value or env:VARNAME)")
            r_cred_val = _prompt(logger, f"    Credential value (raw value or env:VARNAME)")
            if r_source:
                # Store reference repo secret in the credential store, reference as cred:<key>
                ref_cred_config_ref = ""
                if r_cred_val:
                    ref_cred_config_ref = store_secret("credentialkey", r_cred_val, "CREDENTIAL_TOKEN")
                    credential_store.add(key="CREDENTIAL_TOKEN", value=r_cred_val)
                reference_repos.append({
                    "source": r_source,
                    "repopath": str(Path(clone_root) / f"ref_{i}"),
                    "credentialkey": "CREDENTIAL_TOKEN",
                    "credential_map": {"CREDENTIAL_TOKEN": ref_cred_config_ref} if ref_cred_config_ref else {},
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

    # --- Step 4: Token Mappings for reference repo credentials only ---
    logger.info("Step 4: Token Mappings (raw value or env:VARNAME)")
    all_cred_keys = set()
    for r in reference_repos:
        all_cred_keys.add(r.get("credentialkey", "CREDENTIAL_TOKEN"))
    for ck in sorted(all_cred_keys):
        if ck in token_mappings:
            continue  # already set from primary repo
        val = _prompt(logger, f"  {ck} (raw value or env:VARNAME)", default="")
        if val:
            token_mappings[ck] = store_secret("credentialkey", val, ck)
            credential_store.add(key=ck, value=val)

    # Build project config YAML (all inputs collected -- write atomically at end)
    # Quote Windows paths with backslashes - escape backslashes for YAML
    def yaml_quote(s: str) -> str:
        return f'"{s.replace(chr(92), chr(92)+chr(92))}"' if '\\' in s or ':' in s or '/' in s else s
    repo_source_quoted = yaml_quote(repo_source)
    repo_path_quoted = yaml_quote(repo_path)

    repo_entry = f"""  primary:
    source: {repo_source_quoted}
    repopath: {repo_path_quoted}
    credentialkey: {credential_key}"""
    if build_cmd:
        repo_entry += f"\n    buildcmd: {build_cmd}"
    if test_cmd:
        repo_entry += f"\n    testcmd: {test_cmd}"
    if lint_cmd:
        repo_entry += f"\n    lintcmd: {lint_cmd}"

    ref_section = "  reference: []\n"
    if reference_repos:
        ref_section = "  reference:\n"
        for r in reference_repos:
            r_source_quoted = yaml_quote(r["source"])
            r_path_quoted = yaml_quote(r["repopath"])
            ref_section += f"    - source: {r_source_quoted}\n"
            ref_section += f"      repopath: {r_path_quoted}\n"
            ref_section += f"      credentialkey: {r['credentialkey']}\n"
            if r.get("credential_map"):
                for ck, cm in r["credential_map"].items():
                    if "env" in cm:
                        ref_section += f"      credential_map:\n        {ck}: env:{cm['env']}\\n"
                    elif "raw" in cm:
                        ref_section += f"      credential_map:\n        {ck}: {cm['raw']}\\n"

    data_section = "  database:\\n    schema_source: null\\n    migrations_path: null\\n  other: []\\n"
    if database_config:
        data_section = "  data:\\n    database:\\n"
        ds = database_config.get("schema_source") or "null"
        mp = database_config.get("migrations_path") or "null"
        ds_quoted = yaml_quote(ds) if ds else "null"
        mp_quoted = yaml_quote(mp) if mp else "null"
        data_section += f"      schema_source: {ds_quoted}\\n      migrations_path: {mp_quoted}\\n"

    tokens_section = "tokens: {}\\n"
    if token_mappings:
        tokens_section = "tokens:\\n"
        for ck, ref in token_mappings.items():
            if ref:
                tokens_section += f"  {ck}: {_yaml_str(ref)}\\n"

    project_config_yaml = f"""name: {project}
repos:
{repo_entry}
{ref_section}{data_section}{tokens_section}"""

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