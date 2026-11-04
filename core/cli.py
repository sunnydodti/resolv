"""
Resolv CLI Entry Point.
Single entry point with operational control flags and provider selection menu.
All output passes through ResolvLogger facade.
FAIL EARLY: No fallbacks, no defaults, no auto-selection. If anything is missing, fail at startup.
"""
import click
import os
import uuid
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict

from core.logger import ResolvLogger, COLORS
from config.models import load_global_config, load_project_config, ProjectConfig
from core.graph import build_graph, load_state_from_checkpoint


# =============================================================================
# Project Discovery (read-only, no auto-selection)
# =============================================================================
def discover_projects() -> List[str]:
    """List available project configs from config/projects/. No auto-selection."""
    projects_dir = Path("config/projects")
    if not projects_dir.exists():
        return []
    projects = []
    for f in projects_dir.glob("*.yaml"):
        projects.append(f.stem)
    return sorted(projects)


def validate_project_exists(project_name: str) -> bool:
    """Check if a project config file exists."""
    return Path(f"config/projects/{project_name}.yaml").exists()


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
# ANSI Color Helper (matches HLD specification)
# =============================================================================
def colorize(level: str, message: str) -> str:
    """Wrap message with ANSI TrueColor based on log level tag."""
    color = COLORS.get(level, COLORS["RESET"])
    return f"{color}[{level}]{COLORS['RESET']} {message}"


def prompt_vertical(message: str, options: list, default: Optional[str] = None) -> str:
    """
    Display a vertical numbered prompt with defaults in brackets.
    Matches the HLD CLI GUI specification.
    """
    click.echo(colorize("?", message))
    for i, opt in enumerate(options, 1):
        default_marker = " [default]" if default and str(i) == str(default) else ""
        click.echo(f"    {i}. {opt}{default_marker}")
    default_str = str(default) if default else ""
    choice = click.prompt(
        colorize("?", f"Choice [1-{len(options)}] (default: {default_str or '1'})"),
        type=click.Choice([str(i) for i in range(1, len(options) + 1)]),
        default=str(default or 1),
        show_default=False,
    )
    return choice


# =============================================================================
# Provider Selection Menu (NO auto-selection — must be explicit)
# =============================================================================
def select_llm_provider(logger: ResolvLogger, global_config) -> str:
    """
    Display provider selection menu.
    User MUST select explicitly. No auto-selection even if only one provider exists.
    """
    providers = list(global_config.providers.keys())
    default_provider = global_config.default_provider

    if not providers:
        logger.error("No LLM providers configured in config/resolv.yaml")
        logger.info("Add at least one provider under 'providers:' section")
        raise SystemExit(1)

    click.echo()
    click.echo(colorize("?", "Select LLM Provider:"))
    for i, prov in enumerate(providers, 1):
        marker = " [default]" if prov == default_provider else ""
        click.echo(f"    {i}. {prov}{marker}")

    default_idx = providers.index(default_provider) + 1 if default_provider in providers else 1
    choice = click.prompt(
        colorize("?", f"Choice [1-{len(providers)}] (default: {default_idx})"),
        type=click.Choice([str(i) for i in range(1, len(providers) + 1)]),
        default=str(default_idx),
        show_default=False,
    )
    selected = providers[int(choice) - 1]
    logger.info(f"LLM provider selected: {selected}")
    return selected


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
# Main CLI Group
# =============================================================================
@click.group()
@click.option('--project', help='Target project configuration')
@click.option('--verbose', is_flag=True, help='Enable verbose output')
@click.pass_context
def main(ctx, project, verbose):
    """Resolv: Autonomous Issue-to-PR CLI Agent"""
    logger = ResolvLogger(verbose=verbose)
    ctx.obj = logger

    # Load global config (fail fast if missing)
    try:
        global_config = load_global_config()
        logger.info(f"Loaded global config: {global_config.default_provider}")
    except Exception as e:
        logger.error(f"Failed to load global config: {e}")
        ctx.exit(1)

    ctx.obj._global_config = global_config

    # Load project config if --project was provided (optional at group level, required at run level)
    if project:
        if not validate_project_exists(project):
            logger.error(f"Project configuration not found: '{project}'")
            available = discover_projects()
            if available:
                logger.info(f"Available projects: {', '.join(available)}")
            ctx.exit(1)
        try:
            project_config = load_project_config(project)
            ctx.obj._project_config = project_config
            logger.success(f"Project config loaded: {project_config.name}")
        except Exception as e:
            logger.error(f"Failed to load project config '{project}': {e}")
            ctx.exit(1)


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
    except Exception as e:
        logger.error(f"Failed to load global config: {e}")
        ctx.exit(1)

    project_name = project or (ctx.obj._project_config.name if hasattr(ctx.obj, '_project_config') and ctx.obj._project_config else None)
    if not project_name:
        logger.error("--project is required. Use --project <name> or set it on the main command.")
        ctx.exit(1)

    # Load project config (fail fast)
    try:
        project_config = load_project_config(project_name)
    except Exception as e:
        logger.error(f"Failed to load project config '{project_name}': {e}")
        ctx.exit(1)

    # Provider selection: --provider CLI option required (no auto-selection, no fallback)
    if provider:
        selected_provider = provider
        logger.info(f"LLM provider specified via --provider: {selected_provider}")
    elif hasattr(ctx.obj, '_global_config') and ctx.obj._global_config:
        # No --provider: require user to specify
        available = list(ctx.obj._global_config.providers.keys())
        default_provider = ctx.obj._global_config.default_provider
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


if __name__ == '__main__':
    main()
