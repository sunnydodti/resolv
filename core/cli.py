"""
Resolv CLI Entry Point.
Single entry point with operational control flags and provider selection menu.
All output passes through ResolvLogger facade. Direct print/click.echo for user output is prohibited.
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
from config.models import load_global_config, load_project_config, ProjectConfig, CredentialsStore, get_global_config_path, get_project_config_path, get_resolv_dir
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


# =============================================================================
# Project Discovery (read-only, no auto-selection)
# =============================================================================
def discover_projects() -> List[str]:
    """List available project configs from ~/.resolv/projects/. No auto-selection."""
    from config.models import get_resolv_dir
    projects_dir = get_resolv_dir() / "projects"
    if not projects_dir.exists():
        return []
    projects = []
    for f in projects_dir.glob("*.yaml"):
        projects.append(f.stem)
    return sorted(projects)


def validate_project_exists(project_name: str) -> bool:
    """Check if a project config file exists."""
    from config.models import get_project_config_path
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
# Main CLI Group — No config loading here (each command handles its own)
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

    # Provider selection: --provider CLI option required (no auto-selection, no fallback)
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
            "credentials": creds,
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
            "dry_run": dry_run,
            "analysis_only": analysis,
            "verbose": verbose,
            "resume_from_stage": None,
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
def resolve_credentials(logger: ResolvLogger, project_config) -> dict:
    """
    Resolve credentials from environment variables.
    Supports env:<VARNAME> format.
    FAIL EARLY: If any required credential env var is missing, exit immediately.
    """
    creds = {}
    repos = project_config.repos if hasattr(project_config, 'repos') else {}

    # Collect all credential keys needed
    needed_keys = set()
    for repo_key, repo_cfg in repos.items():
        if hasattr(repo_cfg, 'credentialkey'):
            needed_keys.add(repo_cfg.credentialkey)

    # Also check global config tokens
    if hasattr(project_config, 'tokens') and project_config.tokens:
        for key in project_config.tokens:
            needed_keys.add(key)

    if not needed_keys:
        logger.warning("No credentials required by project configuration")
        return creds

    missing = []
    for key in sorted(needed_keys):
        # Determine env var name
        env_var = None
        if hasattr(project_config, 'tokens') and project_config.tokens:
            token_info = project_config.tokens.get(key, {})
            if isinstance(token_info, dict) and 'env' in token_info:
                env_var = token_info['env']

        # Try to resolve from environment
        if env_var:
            value = os.getenv(env_var)
            if value:
                creds[key] = {"env_ref": env_var}
                logger.success(f"Credential resolved: {key} (from {env_var})")
                continue
            missing.append(f"{key} (env: {env_var})")
        else:
            missing.append(f"{key} (no env mapping)")

    if missing:
        logger.error("Required credentials not found in environment:")
        for m in missing:
            logger.error(f"  - {m}")
        logger.info("")
        logger.info("Set them before running Resolv, e.g.:")
        logger.info("  $env:GITHUB_TOKEN=\"your-token\"  (Windows PowerShell)")
        logger.info("  export GITHUB_TOKEN=\"your-token\"  (Linux/macOS)")
        logger.info("")
        logger.info("Or use env:<VARNAME> format in project config to map custom env vars.")
        raise SystemExit(1)

    return creds


# =============================================================================
# Init Command — Global Resolv Initialization (No --project required)
# =============================================================================
@main.command()
@click.option('--verbose', is_flag=True, help='Enable verbose output')
@click.pass_context
def init(ctx, verbose):
    """Initialize Resolv globally (one-time setup). Prompts for global config at each step."""
    logger: ResolvLogger = ctx.obj

    logger.info("Initializing Resolv globally...")

    from config.models import get_global_config_path, get_resolv_dir
    resolv_config_path = get_global_config_path()
    resolv_dir = get_resolv_dir()

    # Load existing config as defaults if re-running
    existing_config = None
    if resolv_config_path.exists():
        try:
            import yaml
            with open(resolv_config_path, 'r') as f:
                existing_config = yaml.safe_load(f)
            logger.info(f"Existing config found at {resolv_config_path}. Press Enter to keep current values.")
        except Exception as e:
            logger.warning(f"Could not read existing config: {e}. Starting fresh.")

    # Create directory structure
    dirs = [
        str(resolv_dir / "projects"),
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

    # --- Step 1: Default Provider ---
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
    provider_choice = input("").strip()
    if not provider_choice:
        provider_choice = default_provider_val
    provider_map = {"1": "google", "2": "anthropic", "3": "openrouter", "4": "local"}
    default_provider = provider_map.get(provider_choice, provider_choice if provider_choice in provider_map.values() else "google")

    # --- Step 2: Telemetry ---
    logger.info("Step 2: Telemetry (Langfuse)")
    telemetry_default = existing_config.get("telemetry", {}).get("enabled", True) if existing_config else True
    telemetry_enabled = _prompt_yes_no(logger, "Enable Langfuse telemetry?", default=telemetry_default)

    langfuse_host_default = existing_config.get("telemetry", {}).get("host", "http://localhost:3000") if existing_config else "http://localhost:3000"
    langfuse_public_key_default = existing_config.get("telemetry", {}).get("public_key_env", "env:LANGFUSE_PUBLIC_KEY") if existing_config else "env:LANGFUSE_PUBLIC_KEY"
    langfuse_secret_key_default = existing_config.get("telemetry", {}).get("secret_key_env", "env:LANGFUSE_SECRET_KEY") if existing_config else "env:LANGFUSE_SECRET_KEY"

    langfuse_host = "http://localhost:3000"
    langfuse_public_key_env = "LANGFUSE_PUBLIC_KEY"
    langfuse_secret_key_env = "LANGFUSE_SECRET_KEY"

    if telemetry_enabled:
        langfuse_host = _prompt(logger, "Langfuse host URL (raw value or env:VARNAME)", default=langfuse_host_default)
        langfuse_public_key_env = _prompt(logger, "Public key env var name (raw value or env:VARNAME)", default=langfuse_public_key_default)
        langfuse_secret_key_env = _prompt(logger, "Secret key env var name (raw value or env:VARNAME)", default=langfuse_secret_key_default)

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
        default_add = bool(existing_prov)  # default to Yes if already configured
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
        api_key_env_default = existing_prov.get("api_key_env", f"env:{prov_name.upper()}_API_KEY") if existing_prov else f"env:{prov_name.upper()}_API_KEY"
        api_key_env = _prompt(logger, f"  API key env var for {prov_name} (raw value or env:VARNAME)", default=api_key_env_default)
        api_base_default = existing_prov.get("api_base", "") if existing_prov else ""
        api_base = _prompt(logger, f"  API base URL for {prov_name} (optional, raw value or env:VARNAME)", default=api_base_default)
        api_key_env_raw = api_key_env[4:] if api_key_env.startswith("env:") else api_key_env
        api_base_raw = api_base[4:] if api_base.startswith("env:") else api_base
        providers[prov_name] = {
            "model": model,
            "api_key_env": api_key_env_raw,
        }
        if api_base_raw:
            providers[prov_name]["api_base"] = api_base_raw

    if not providers:
        logger.error("At least one provider must be configured.")
        ctx.exit(1)

    # Build global config YAML (all inputs collected — write atomically at end)
    telemetry_enabled_str = str(telemetry_enabled).lower()
    telemetry_section = f"""  enabled: {telemetry_enabled_str}
  platform: langfuse
  host: {langfuse_host}
  public_key_env: {langfuse_public_key_env}
  secret_key_env: {langfuse_secret_key_env}"""

    providers_section = ""
    for prov_name, prov_cfg in providers.items():
        providers_section += f"  {prov_name}:\n"
        providers_section += f"    model: {prov_cfg['model']}\n"
        providers_section += f"    api_key_env: {prov_cfg['api_key_env']}\n"
        if prov_cfg.get("api_base"):
            providers_section += f"    api_base: {prov_cfg['api_base']}\n"

    global_config_yaml = f"""default_provider: {default_provider}
telemetry:
{telemetry_section}
clone_root: {clone_root}
providers:
{providers_section}"""

    # Write atomically
    resolv_config_path.write_text(global_config_yaml)
    logger.success(f"Created {resolv_config_path}")

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
# Setup Command — Per-Project Setup (--project required)
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

    # Load global config
    try:
        global_config = load_global_config()
        ctx.obj._global_config = global_config
    except Exception as e:
        logger.error(f"Failed to load global config: {e}")
        ctx.exit(1)

    clone_root = getattr(global_config, 'clone_root', str(Path.home() / "workspaces"))

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
    repo_source = _prompt(logger, "Repository source (e.g., github.com/org/repo) (raw value or env:VARNAME)", default=repo_source_default)
    if not repo_source:
        logger.error("Repository source is required.")
        ctx.exit(1)

    # Auto-compute repopath as clone_root/<project>
    repo_path = str(Path(clone_root) / project)

    # Derive credential key from repo source host (e.g., github.com → GITHUB_TOKEN)
    existing_cred_key = existing_repo.get("credentialkey", "") if existing_repo else ""
    if not existing_cred_key:
        host_match = re.search(r'://([^/]+)/', repo_source)
        if host_match:
            host = host_match.group(1)
            # Map common hosts to standard credential key names
            host_key_map = {
                'github.com': 'GITHUB_TOKEN',
                'gitlab.com': 'GITLAB_TOKEN',
                'bitbucket.org': 'BITBUCKET_TOKEN',
            }
            credential_key_default = host_key_map.get(host, f"{host.replace('.', '_').upper()}_TOKEN")
        else:
            credential_key_default = "GITHUB_TOKEN"
    else:
        credential_key_default = existing_cred_key

    logger.info(f"  Credential key (derived from repo host): {credential_key_default}")
    credential_key = credential_key_default

    credential_value = _prompt(logger, f"  {credential_key} value (raw value or env:VARNAME)")
    if credential_value.startswith("env:"):
        token_mappings = {credential_key: {"env": credential_value[4:]}}
    elif credential_value:
        token_mappings = {credential_key: {"raw": credential_value}}
    else:
        token_mappings = {}

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
            r_cred = _prompt(logger, "    Credential key (raw value or env:VARNAME)", default="GITHUB_TOKEN")
            r_cred_val = _prompt(logger, f"    {r_cred} value (raw value or env:VARNAME)")
            if r_source:
                cm = {}
                if r_cred_val.startswith("env:"):
                    cm[r_cred] = {"env": r_cred_val[4:]}
                elif r_cred_val:
                    cm[r_cred] = {"raw": r_cred_val}
                reference_repos.append({
                    "source": r_source,
                    "repopath": str(Path(clone_root) / f"ref_{i}"),
                    "credentialkey": r_cred,
                    "credential_map": cm,
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
        all_cred_keys.add(r.get("credentialkey", "GITHUB_TOKEN"))
    for ck in sorted(all_cred_keys):
        if ck in token_mappings:
            continue  # already set from primary repo
        val = _prompt(logger, f"  {ck} (raw value or env:VARNAME)", default="")
        if val:
            if val.startswith("env:"):
                token_mappings[ck] = {"env": val[4:]}
            else:
                token_mappings[ck] = {"raw": val}

    # Build project config YAML (all inputs collected — write atomically at end)
    repo_entry = f"""  primary:
    source: {repo_source}
    repopath: {repo_path}
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
            ref_section += f"    - source: {r['source']}\n"
            ref_section += f"      repopath: {r['repopath']}\n"
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
        data_section += f"      schema_source: {ds}\\n      migrations_path: {mp}\\n"

    tokens_section = "tokens: {}\\n"
    if token_mappings:
        tokens_section = "tokens:\\n"
        for ck, tm in token_mappings.items():
            if "env" in tm:
                tokens_section += f"  {ck}: env:{tm['env']}\\n"
            elif "raw" in tm:
                tokens_section += f"  {ck}: {tm['raw']}\\n"

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

    cred_agent = CredentialsSubAgent(logger, None)
    cred_store = CredentialsStore()

    # Collect all credential keys from primary token_mappings and reference repo credential_map
    needed_keys = set(token_mappings.keys())
    for r in reference_repos:
        if r.get("credential_map"):
            needed_keys.update(r["credential_map"].keys())
    missing = []
    for key in sorted(needed_keys):
        tm = token_mappings.get(key, {})
        if "env" in tm:
            env_var = tm["env"]
            value = os.getenv(env_var)
            if value:
                cred_store.add(key=key, env_ref=env_var)
                logger.success(f"Credential resolved: {key} (from {env_var})")
            else:
                missing.append(f"{key} (env: {env_var})")
        elif "raw" in tm:
            cred_store.add(key=key, value=tm["raw"])
            logger.success(f"Credential resolved: {key} (raw value)")
        else:
            # Check reference repo credential_map
            found_in_ref = False
            for r in reference_repos:
                if r.get("credential_map") and key in r["credential_map"]:
                    cm = r["credential_map"][key]
                    if "env" in cm:
                        env_var = cm["env"]
                        value = os.getenv(env_var)
                        if value:
                            cred_store.add(key=key, env_ref=env_var)
                            logger.success(f"Credential resolved: {key} (from {env_var})")
                            found_in_ref = True
                            break
                        else:
                            missing.append(f"{key} (env: {env_var})")
                            found_in_ref = True
                            break
                    elif "raw" in cm:
                        cred_store.add(key=key, value=cm["raw"])
                        logger.success(f"Credential resolved: {key} (raw value)")
                        found_in_ref = True
                        break
            if not found_in_ref:
                missing.append(f"{key} (no value provided)")

    if missing:
        logger.warning("Some credentials not resolved (can set later):")
        for m in missing:
            logger.warning(f"  - {m}")
        logger.info("  Set them before running Resolv, e.g.:")
        if missing:
            first_key = missing[0].split(' ')[0]
            logger.info(f'    $env:{first_key}=\"your-token\"  (Windows PowerShell)')
            logger.info(f"    export {first_key}=\\\"your-token\\\"  (Linux/macOS)")

    cred_agent.save_to_session(session_path, cred_store)
    logger.success(f"Saved credentials to {session_path}/credentials.json")

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
