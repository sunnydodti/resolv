"""
Resolv CLI Entry Point.
Single entry point with operational control flags and provider selection menu.
All output passes through ResolvLogger facade.
"""
import click
from typing import Optional
from core.logger import ResolvLogger, COLORS
from config.models import load_global_config, load_project_config
from core.graph import build_graph, load_state_from_checkpoint


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
    click.echo(colorize("?", f"Choice [1-{len(options)}] (default: {default_str or '1'}): ", ), nl=False)
    choice = click.prompt("", type=click.Choice([str(i) for i in range(1, len(options) + 1)]), default=str(default or 1), show_default=False)
    return choice


# =============================================================================
# Provider Selection Menu
# =============================================================================
def select_llm_provider(logger: ResolvLogger, global_config) -> str:
    """
    Display provider selection menu.
    OpenRouter is default at start per requirements.
    """
    providers = list(global_config.providers.keys())
    default_provider = global_config.default_provider

    click.echo()
    click.echo(colorize("?", "Select LLM Provider:"))
    for i, prov in enumerate(providers, 1):
        marker = " [default]" if prov == default_provider else ""
        click.echo(f"    {i}. {prov}{marker}")

    default_idx = providers.index(default_provider) + 1 if default_provider in providers else 1
    click.echo(colorize("?", f"Choice [1-{len(providers)}] (default: {default_idx}): ", ), nl=False)
    choice = click.prompt("", type=click.Choice([str(i) for i in range(1, len(providers) + 1)]), default=str(default_idx), show_default=False)
    selected = providers[int(choice) - 1]
    logger.info(f"LLM provider selected: {selected}")
    return selected


# =============================================================================
# Credential Prompting
# =============================================================================
def prompt_for_credentials(logger: ResolvLogger, project_config) -> dict:
    """
    Prompt user for credentials if not already available.
    Supports raw values or env:<varname> format.
    Stores in credentials.json.
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
        return creds

    click.echo()
    click.echo(colorize("?", "Credential Configuration:"))
    click.echo("  Enter values directly, or use env:<VARNAME> for environment variables.")

    for key in sorted(needed_keys):
        val = click.prompt(f"  {key}", type=str, default="", show_default=False)
        if val.startswith("env:"):
            env_var = val[4:]
            creds[key] = {"env_ref": env_var}
        else:
            creds[key] = {"value": val}

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

    if project:
        logger.info(f"Initializing resolv session for project: {project}")
        try:
            project_config = load_project_config(project)
            ctx.obj._project_config = project_config
            logger.success(f"Project config loaded: {project_config.name}")
        except Exception as e:
            logger.error(f"Failed to load project config '{project}': {e}")
            ctx.exit(1)
    else:
        logger.warning("No --project specified. Using default configuration.")


# =============================================================================
# Run Command
# =============================================================================
@main.command()
@click.argument('issue_reference')
@click.option('--project', help='Target project configuration')
@click.option('--analysis', is_flag=True, help='Halt after Stage 2 (Plan), exit code 0')
@click.option('--resume', is_flag=True, help='Resume from last recorded stage')
@click.option('--dry-run', is_flag=True, help='Run through Stage 5, skip Stage 6 (Publish)')
@click.option('--verbose', is_flag=True, help='Enable verbose output')
@click.option('--max-healing-turns', type=int, default=3, help='Max self-healing turns (default: 3)')
@click.pass_context
def run(ctx, issue_reference, project, analysis, resume, dry_run, verbose, max_healing_turns):
    """Run Resolv on an issue reference"""
    logger: ResolvLogger = ctx.obj

    # Load configs
    try:
        global_config = load_global_config()
    except Exception as e:
        logger.error(f"Failed to load global config: {e}")
        ctx.exit(1)

    project_name = project or "default"
    try:
        project_config = load_project_config(project_name)
    except Exception as e:
        logger.error(f"Failed to load project config '{project_name}': {e}")
        ctx.exit(1)

    # Provider selection menu (OpenRouter default)
    selected_provider = select_llm_provider(logger, global_config)

    # Credential prompting (fail early if missing)
    creds = prompt_for_credentials(logger, project_config)
    if not creds:
        logger.warning("No credentials configured. Some operations may fail.")

    # Extract issue ID from reference
    issue_id = issue_reference.split('/')[-1] if '/' in issue_reference else issue_reference

    # Build session path
    session_path = f".resolv/sessions/{project_name}/{issue_id}"

    # Handle resume
    initial_state = None
    if resume:
        from core.graph import load_state_from_checkpoint
        saved = load_state_from_checkpoint(session_path)
        if saved:
            logger.info(f"Resuming from stage: {saved.get('current_stage', 'unknown')}")
            # Re-execute current stage from scratch
            initial_state = saved
        else:
            logger.warning("No checkpoint found. Starting fresh.")

    # Build initial state
    if not initial_state:
        initial_state = {
            "session_id": str(uuid.uuid4()) if 'uuid' in dir() else "",
            "issue_reference": issue_reference,
            "issue_id": issue_id,
            "project_name": project_name,
            "session_path": session_path,
            "current_stage": "STAGE_0_SETUP",
            "status": "IN_PROGRESS",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
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

    # Import here to avoid circular imports
    import uuid
    from datetime import datetime, timezone
    initial_state["session_id"] = str(uuid.uuid4())
    initial_state["created_at"] = datetime.now(timezone.utc).isoformat()

    # Build and run the graph
    try:
        graph = build_graph()
        logger.info(f"Starting Resolv pipeline for issue: {issue_reference}")

        # Run through stages
        final_state = None
        for event in graph.stream(initial_state, stream_mode="values"):
            final_state = event
            current_stage = event.get("current_stage", "unknown")
            logger.info(f"Stage progress: {current_stage}")

            # Check for analysis-only mode
            if analysis and current_stage == "STAGE_2_PLAN":
                logger.info("--analysis flag set. Halting after Stage 2 (Plan).")
                logger.success("Analysis complete. Exiting cleanly (exit code 0).")
                ctx.exit(0)

        if final_state:
            logger.success(f"Pipeline completed. Final stage: {final_state.get('current_stage')}")
            if final_state.get("pr_url"):
                logger.success(f"Pull Request: {final_state['pr_url']}")
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        if verbose:
            import traceback
            logger.debug(traceback.format_exc())
        ctx.exit(1)


if __name__ == '__main__':
    main()
