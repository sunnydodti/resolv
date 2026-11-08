"""
LangGraph StateGraph for Resolv autonomous agent.
Orchestrates all 7 stages with conditional edges, checkpoints, and resume support.
"""
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from agents.state import ResolvState, SessionMetadata
from core.logger import ResolvLogger
from config.models import (
    GlobalConfig, ProjectConfig, CredentialsStore,
    CodeContext, ResolutionPlan, ReviewResult,
    load_global_config, load_project_config, get_resolv_dir
)


def _get_logger(state: ResolvState) -> ResolvLogger:
    """Get logger from state, creating a fallback if not present.

    _logger is not serializable through LangGraph's MemorySaver checkpointer,
    so it may be lost between stage nodes. This helper ensures every stage
    has a working logger. Debug messages always go to the session log file;
    they appear on stdout only when verbose=True.
    """
    logger = state.get("_logger")
    if logger is None:
        verbose = state.get("verbose", False)
        log_file = state.get("log_file")
        logger = ResolvLogger(verbose=verbose, log_file=log_file)
    return logger


def _planned_file_targets(plan_data: Any) -> list:
    """Extract real file paths from plan steps, filtering out URLs and non-file targets."""
    if not plan_data:
        return []
    planned = []
    for step in plan_data:
        if isinstance(step, dict):
            target = step.get("target_file", "")
            action = step.get("action", "")
        else:
            target = getattr(step, "target_file", "")
            action = getattr(step, "action", "")
        # Skip URLs and empty targets
        if not target or target.startswith(("http://", "https://")):
            continue
        planned.append(target)
    return planned


def _changes_were_planned(state: ResolvState) -> bool:
    """Return True if the plan contains real file-change targets."""
    plan_data = state.get("plan_data", [])
    return len(_planned_file_targets(plan_data)) > 0


def _planned_changes_applied(state: ResolvState) -> tuple[bool, list, list]:
    """
    Compare planned file targets against what was actually applied.

    Returns (applied, planned_files, applied_files):
      - applied: True if every planned file was applied (or nothing was planned)
      - planned_files: list of real file targets from the plan
      - applied_files: list of files actually modified
    """
    planned = _planned_file_targets(state.get("plan_data", []))
    applied = state.get("modified_files", []) or []

    if not planned:
        # Nothing was planned — treat as no-op, valid
        return True, [], applied

    planned_set = set(planned)
    applied_set = set(applied)

    # All planned files must be in applied files
    all_applied = planned_set.issubset(applied_set)
    return all_applied, planned, applied


# =============================================================================
# Stage Node Functions
# =============================================================================

def stage_0_setup(state: ResolvState) -> ResolvState:
    """
    Stage 0: Initialization & Setup.
    - Create session workspace
    - Load credentials
    - Resolve repository paths
    - Prepare base and feature branches
    - Initialize metadata.json
    """
    logger = _get_logger(state)
    project_name: str = state.get("project_name")
    issue_reference: str = state.get("issue_reference")
    issue_id: str = state.get("issue_id", "") or issue_reference.split("/")[-1] if issue_reference else ""

    # FAIL EARLY: Required state fields must be present
    if not project_name:
        logger.error("Missing required state field: project_name")
        raise ValueError("Missing project_name in state")
    if not issue_reference:
        logger.error("Missing required state field: issue_reference")
        raise ValueError("Missing issue_reference in state")

    logger.info(f"Stage 0: Setup — Establishing isolated session workspace")

    # Create session workspace under Resolv home (~/.resolv/sessions/...)
    session_path = Path(get_resolv_dir() / "sessions" / project_name / issue_id)
    session_path.mkdir(parents=True, exist_ok=True)

    logger.debug(f"project_name={project_name}")
    logger.debug(f"issue_reference={issue_reference}")
    logger.debug(f"issue_id={issue_id}")
    logger.debug(f"session_path={session_path}")
    logger.debug(f"max_healing_turns={state.get('max_healing_turns', 3)}")
    logger.debug(f"dry_run={state.get('dry_run', False)}")
    logger.debug(f"analysis_only={state.get('analysis_only', False)}")
    logger.debug(f"verbose={state.get('verbose', False)}")
    logger.debug(f"log_file={state.get('log_file')}")

    # Initialize metadata
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    metadata = SessionMetadata(
        session_id=session_id,
        issue_reference=issue_reference,
        current_stage="STAGE_0_SETUP",
        status="IN_PROGRESS",
        created_at=now,
        updated_at=now,
        max_healing_turns=state.get("max_healing_turns", 3),
        dry_run=state.get("dry_run", False),
        analysis_only=state.get("analysis_only", False),
    )

    # Save metadata.json
    metadata_path = session_path / "metadata.json"
    with open(metadata_path, "w") as f:
        json.dump(metadata.model_dump(), f, indent=2, default=str)

    # Initialize credentials store from state (loaded from global credential store)
    from agents.tools.credentials import CredentialsSubAgent
    from config.models import CredentialsStore, save_credentials
    from agents.tools.github_platform import GitHubPlatformSubAgent
    
    cred_agent = CredentialsSubAgent(logger, None)
    cred_store = CredentialsStore()
    state_creds = state.get("credentials")
    if state_creds:
        for key, val in state_creds.get("credentials", {}).items():
            cred_store.add(
                key=val.get("key", key),
                value=val.get("value"),
                env_ref=val.get("env_ref")
            )
    cred_agent.save_to_session(str(session_path), cred_store)

    # Save credentials.json
    save_credentials(str(session_path), cred_store)

    # Initialize project_config early
    project_config = state.get("project_config", {})

    # Resolve primary repo full name
    primary = {}
    if isinstance(project_config, dict):
        repos = project_config.get("repos", {})
        primary = repos.get("primary", {})
    
    repo_full_name = None
    if isinstance(primary, dict):
        base = primary.get("base")
        path = primary.get("path")
        if base == "github.com" and path:
            repo_full_name = path

    # Pre-flight credential validation
    from agents.tools.github_platform import GitHubPlatformSubAgent
    platform_agent = GitHubPlatformSubAgent(logger, project_config)
    platform_agent._authenticate(credential_store=cred_store)
            
    if not platform_agent.validate_credentials(repo_full_name=repo_full_name):
        logger.error("GitHub credential validation failed. Cannot proceed.")
        raise RuntimeError("GitHub authentication failed. Please check your GitHub token and repository access permissions.")

    # Clone the primary repository into clone_root/<project>
    global_config = state.get("global_config", {})
    if isinstance(global_config, dict):
        clone_root = global_config.get("clone_root", str(get_resolv_dir() / "workspaces"))
    else:
        clone_root = getattr(global_config, 'clone_root', str(get_resolv_dir() / "workspaces"))

    project_config = state.get("project_config", {})
    if isinstance(project_config, dict):
        repos = project_config.get("repos", {})
        primary = repos.get("primary", {})
    else:
        repos = getattr(project_config, 'repos', {})
        primary = repos.get("primary", {}) if hasattr(repos, 'get') else {}

    repo_base = primary.get("base", "") if isinstance(primary, dict) else ""
    repo_path_part = primary.get("path", "") if isinstance(primary, dict) else ""

    if repo_base and repo_path_part:
        repo_url = f"https://{repo_base}/{repo_path_part}"
        target_repo_path = str(Path(clone_root) / project_name)

        from agents.tools.remote_git import RemoteGitSubAgent
        remote_agent = RemoteGitSubAgent(logger, None)
        try:
            remote_agent.clone_repo(repo_url, target_repo_path)
        except RuntimeError as e:
            logger.error(str(e))
            raise

        logger.info(f"Repository ready at {target_repo_path}")
    else:
        logger.warning(
            "No repo base/path in project config — skipping clone. "
            "Run 'resolv setup --project <name>' to configure."
        )

    logger.success(f"Stage 0 Complete — Workspace ready at {session_path}")

    return {
        **state,
        "session_id": session_id,
        "session_path": str(session_path),
        "current_stage": "STAGE_0_SETUP",
        "status": "IN_PROGRESS",
        "created_at": now,
        "updated_at": now,
        "worktree_path": None,
        "modified_files": [],
        "healing_turns": 0,
        "pr_url": None,
        "pr_draft": False,
        "branch_name": None,
        "repo_full_name": repo_full_name,
        # Persist config, issue_id, and credentials so subsequent stages don't lose them
        "project_config": project_config,
        "issue_id": issue_id,
        "credentials_store": cred_store.model_dump(),
    }


def stage_1_analyze(state: ResolvState) -> ResolvState:
    """
    Stage 1: Analyze — Context gathering and semantic exploration.
    Produces context.json and analysis.md.
    """
    logger = _get_logger(state)
    logger.info("Stage 1: Analyze — Ingesting issue and exploring codebase...")

    project_config = state.get("project_config", {})
    issue_reference = state.get("issue_reference", "")

    logger.debug(f"issue_reference={issue_reference}")

    # Extract repo paths from project config
    repo_paths = []
    repos = project_config.get("repos", {}) if isinstance(project_config, dict) else {}
    for repo_key, repo_cfg in repos.items():
        if isinstance(repo_cfg, dict) and "repopath" in repo_cfg:
            repo_paths.append(repo_cfg["repopath"])

    logger.debug(f"repo_paths={repo_paths}")

    # Delegate to ContextAgent
    from agents.context_agent import ContextAgent
    context_agent = ContextAgent(logger, project_config)
    context_result = context_agent.execute(issue_reference, repo_paths)

    # Save context.json
    session_path = Path(state["session_path"])
    context_path = session_path / "context.json"
    with open(context_path, "w") as f:
        json.dump(context_result, f, indent=2, default=str)

    # Generate analysis.md
    from core.markdown_gen import generate_analysis_md
    analysis_md_path = session_path / "analysis.md"
    generate_analysis_md(context_result, str(analysis_md_path))

    logger.success("Stage 1 Complete — Generated context.json & analysis.md")

    return {
        **state,
        "current_stage": "STAGE_1_ANALYZE",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "context_data": context_result,
        "analysis_md_path": str(analysis_md_path),
    }


def stage_2_plan(state: ResolvState) -> ResolvState:
    """
    Stage 2: Plan — Synthesize architectural roadmap.
    Produces plan.json and plan.md.
    """
    logger = _get_logger(state)
    logger.info("Stage 2: Plan — Synthesizing architectural roadmap...")

    context_data = state.get("context_data", {})
    project_config = state.get("project_config", {})

    logger.debug(f"context_data keys={list(context_data.keys()) if isinstance(context_data, dict) else type(context_data)}")
    logger.debug(f"symbols count={len(context_data.get('symbols', [])) if isinstance(context_data, dict) else 'N/A'}")
    logger.debug(f"source_files count={len(context_data.get('source_files', [])) if isinstance(context_data, dict) else 'N/A'}")

    # Create LLM gateway and select provider
    from agents.llm_gateway import LiteLLMGateway
    from config.models import CredentialsStore, GlobalConfig, ProviderConfig
    cred_store = CredentialsStore()
    # Try credentials_store first (set by stage 0), fall back to credentials (from cli.py initial state)
    state_creds = state.get("credentials_store") or state.get("credentials")
    logger.debug(f"credentials_store in state: {bool(state_creds)}")
    if state_creds:
        logger.debug(f"credentials_store keys: {list(state_creds.get('credentials', {}).keys())}")
        for key, val in state_creds.get("credentials", {}).items():
            cred_store.add(
                key=val.get("key", key),
                value=val.get("value"),
                env_ref=val.get("env_ref")
            )
    logger.debug(f"cred_store keys after rebuild: {list(cred_store.credentials.keys())}")
    # Reconstruct GlobalConfig from stored dict (state stores model_dump())
    gc_dict = state.get("global_config", {})
    if isinstance(gc_dict, dict):
        providers = {}
        for name, prov in gc_dict.get("providers", {}).items():
            providers[name] = ProviderConfig(**prov)
        default_provider = gc_dict.get("default_provider", "openrouter")
        # Ensure default_provider exists in configured providers
        if default_provider not in providers and providers:
            default_provider = next(iter(providers))
        global_config = GlobalConfig(
            default_provider=default_provider,
            telemetry=gc_dict.get("telemetry", {}),
            providers=providers,
            clone_root=gc_dict.get("clone_root"),
        )
    else:
        global_config = gc_dict
    llm_gateway = LiteLLMGateway(logger, global_config, credential_store=cred_store)
    selected_provider = state.get("selected_provider")
    if selected_provider:
        llm_gateway.select_provider(selected_provider)
        logger.info(f"LLM provider selected for planning: {selected_provider}")

    from agents.planner_agent import PlannerAgent
    planner = PlannerAgent(logger, project_config, llm_gateway=llm_gateway, global_config=global_config)
    plan_steps = planner.execute(context_data)

    # Convert Pydantic models to dict for serialization
    plan_data = [step.model_dump() if hasattr(step, "model_dump") else step for step in plan_steps]

    # Save plan.json
    session_path = Path(state["session_path"])
    plan_path = session_path / "plan.json"
    with open(plan_path, "w") as f:
        json.dump(plan_data, f, indent=2, default=str)

    # Generate plan.md
    from core.markdown_gen import generate_plan_md
    plan_md_path = session_path / "plan.md"
    generate_plan_md(plan_data, str(plan_md_path))

    logger.success("Stage 2 Complete — Generated plan.json & plan.md")

    return {
        **state,
        "current_stage": "STAGE_2_PLAN",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "plan_data": plan_data,
        "plan_md_path": str(plan_md_path),
    }


def stage_3_apply(state: ResolvState) -> ResolvState:
    """
    Stage 3: Apply — Create isolated git worktrees and apply code edits.
    """
    logger = _get_logger(state)
    logger.info("Stage 3: Apply — Synthesizing structured code edits in worktree...")

    try:
        return _stage_3_apply_impl(state)
    except PermissionError as e:
        logger.error(f"Permission denied in Stage 3: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        raise


def _stage_3_apply_impl(state: ResolvState) -> ResolvState:
    logger = _get_logger(state)
    plan_steps = state.get("plan_data", [])
    project_config = state.get("project_config", {})

    logger.debug(f"plan_steps count={len(plan_steps) if isinstance(plan_steps, list) else 'N/A'}")
    for i, step in enumerate(plan_steps[:10] if isinstance(plan_steps, list) else []):
        logger.debug(f"  plan step {i}: {step}")

    # Create LLM gateway and select provider for code synthesis
    from agents.llm_gateway import LiteLLMGateway
    from config.models import CredentialsStore, GlobalConfig, ProviderConfig
    cred_store = CredentialsStore()
    # Try credentials_store first (set by stage 0), fall back to credentials (from cli.py initial state)
    state_creds = state.get("credentials_store") or state.get("credentials")
    logger.debug(f"credentials_store in state: {bool(state_creds)}")
    if state_creds:
        logger.debug(f"credentials_store keys: {list(state_creds.get('credentials', {}).keys())}")
        for key, val in state_creds.get("credentials", {}).items():
            cred_store.add(
                key=val.get("key", key),
                value=val.get("value"),
                env_ref=val.get("env_ref")
            )
    logger.debug(f"cred_store keys after rebuild: {list(cred_store.credentials.keys())}")

    # Reconstruct GlobalConfig from stored dict (state stores model_dump())
    gc_dict = state.get("global_config", {})
    if isinstance(gc_dict, dict):
        providers = {}
        for name, prov in gc_dict.get("providers", {}).items():
            providers[name] = ProviderConfig(**prov)
        default_provider = gc_dict.get("default_provider", "openrouter")
        # Ensure default_provider exists in configured providers
        if default_provider not in providers and providers:
            default_provider = next(iter(providers))
        global_config = GlobalConfig(
            default_provider=default_provider,
            telemetry=gc_dict.get("telemetry", {}),
            providers=providers,
            clone_root=gc_dict.get("clone_root"),
        )
    else:
        global_config = gc_dict
    llm_gateway = LiteLLMGateway(logger, global_config, credential_store=cred_store)
    selected_provider = state.get("selected_provider")
    if selected_provider:
        llm_gateway.select_provider(selected_provider)
        logger.info(f"LLM provider selected for coding: {selected_provider}")

    from agents.coding_agent import CodingAgent
    coding_agent = CodingAgent(logger, project_config, llm_gateway=llm_gateway, global_config=global_config)

    # Resolve primary repo path
    primary_repo = "./"
    repos = project_config.get("repos", {}) if isinstance(project_config, dict) else {}
    if "primary" in repos:
        primary_repo = repos["primary"].get("repopath", "./") if isinstance(repos["primary"], dict) else "./"

    # Determine branch name once and persist it
    feature_branch = state.get("branch_name")
    if not feature_branch:
        issue_id = state.get('issue_id') or state.get('issue_reference', 'unknown').split('/')[-1]
        feature_branch = f"resolv/{issue_id}"

    # Create worktree
    worktree_path = coding_agent.git_tool.init_session_workspace(primary_repo, feature_branch)

    # Clean any unstaged changes from previous runs to avoid conflicts
    coding_agent.git_tool.clean_unstaged_changes(worktree_path)

    # Apply planned edits
    from agents.coding_agent import PatchResult
    patch_result: PatchResult = coding_agent.execute(plan_steps, worktree_path)

    logger.success(f"Stage 3 Complete — {len(patch_result.modified_files)} file(s) modified")
    logger.debug(f"worktree_path={worktree_path}")
    logger.debug(f"modified_files={patch_result.modified_files}")
    logger.debug(f"diff_output length={len(patch_result.diff) if patch_result.diff else 0}")

    return {
        **state,
        "current_stage": "STAGE_3_APPLY",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "worktree_path": worktree_path,
        "branch_name": feature_branch,
        "modified_files": patch_result.modified_files,
        "diff_output": patch_result.diff,
    }


def stage_4_build_test(state: ResolvState) -> ResolvState:
    """
    Stage 4: Build / Test — Execute tests with self-healing loop.
    On failure, route back to Stage 3 (if turns < max) or to Stage 6.
    """
    logger = _get_logger(state)
    logger.info("Stage 4: Build / Test — Running sandboxed test suite...")

    project_config = state.get("project_config", {})
    max_turns = state.get("max_healing_turns", 3)
    current_turns = state.get("healing_turns", 0)

    logger.debug(f"max_healing_turns={max_turns}")
    logger.debug(f"healing_turns={current_turns}")

    from agents.tools.sandbox_runner import SandboxRunnerSubAgent
    runner = SandboxRunnerSubAgent(logger, project_config)

    test_cmd = None
    repos = project_config.get("repos", {}) if isinstance(project_config, dict) else {}
    if "primary" in repos and isinstance(repos["primary"], dict):
        test_cmd = repos["primary"].get("testcmd")

    build_cmd = None
    if "primary" in repos and isinstance(repos["primary"], dict):
        build_cmd = repos["primary"].get("buildcmd")

    logger.debug(f"build_cmd={build_cmd}")
    logger.debug(f"test_cmd={test_cmd}")

    # Run build (skip if not configured)
    if not build_cmd:
        logger.warning("No build command configured for this project — skipping build")
    else:
        build_result = runner.run_command(build_cmd)
        if build_result["returncode"] != 0:
            logger.error(f"Build failed: {build_result['stderr']}")
            # Route back to Stage 3 if turns remain
            if current_turns < max_turns:
                return {
                    **state,
                    "current_stage": "STAGE_3_APPLY",
                    "healing_turns": current_turns + 1,
                    "error_trace": build_result["stderr"],
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            else:
                return {
                    **state,
                    "current_stage": "STAGE_6_PUBLISH",
                    "error_trace": build_result["stderr"],
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }

    # Run tests (skip if not configured)
    if not test_cmd:
        logger.warning("No test command configured for this project — skipping tests")
        test_result = {"returncode": 0, "stdout": "", "stderr": "skipped: no test command configured"}
        return {
            **state,
            "current_stage": "STAGE_4_BUILD_TEST",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "test_results": test_result,
            "error_trace": None,
        }
    else:
        test_result = runner.run_command(test_cmd)
        if test_result["returncode"] != 0:
            logger.warning(f"Test failure detected (turn {current_turns + 1}/{max_turns})")
        if current_turns < max_turns:
            return {
                **state,
                "current_stage": "STAGE_3_APPLY",
                "healing_turns": current_turns + 1,
                "error_trace": test_result["stderr"],
                "test_results": test_result,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        else:
            logger.error("Max healing turns reached. Routing to Stage 6 for gap report.")
            return {
                **state,
                "current_stage": "STAGE_6_PUBLISH",
                "healing_turns": current_turns + 1,
                "error_trace": test_result["stderr"],
                "test_results": test_result,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }


def stage_5_review(state: ResolvState) -> ResolvState:
    """
    Stage 5: Review — Audit diff for security and compliance.
    On failure, route back to Stage 1/2.
    """
    logger = _get_logger(state)
    logger.info("Stage 5: Review — Auditing diff for security and compliance...")

    diff_output = state.get("diff_output", "")
    project_config = state.get("project_config", {})

    logger.debug(f"diff_output length={len(diff_output or '')}")
    logger.debug(f"project_config keys={list(project_config.keys()) if isinstance(project_config, dict) else type(project_config)}")

    # Determine what was planned vs what was actually applied
    applied, planned_files, applied_files = _planned_changes_applied(state)

    # If nothing was planned, this is a no-op — skip review gracefully
    if not planned_files:
        logger.warning("No code changes were planned — Stage 5 is a no-op, skipping review")
        return {
            **state,
            "current_stage": "STAGE_5_REVIEW",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "security_result": {"status": "SKIPPED", "reason": "no changes planned"},
            "review_result": {"status": "SKIPPED", "reason": "no changes planned"},
        }

    # If changes were planned but not applied — fail fast
    if not applied:
        logger.error(
            f"Changes were planned for {planned_files} but none were applied. "
            "Stage 3 did not implement the planned changes."
        )
        raise RuntimeError(
            f"Stage 5 failed: planned changes for {planned_files} were not applied by Stage 3. "
            "The coding agent must implement the planned file changes before review."
        )

    # Fail fast: no actual code changes to review
    if not diff_output or not diff_output.strip():
        logger.error("No code changes to review — diff is empty")
        raise RuntimeError(
            "Stage 5 failed: diff is empty. No code changes were produced in Stage 3, "
            "so there is nothing to review for security or compliance."
        )

    from agents.security_agent import SecurityAgent
    from agents.review_agent import ReviewAgent

    security_agent = SecurityAgent(logger, project_config)
    review_agent = ReviewAgent(logger, project_config)

    # Security audit
    security_result = security_agent.execute(diff_output)
    if security_result.get("status") == "FAILED":
        logger.error("Stage 5 Failed — Security violations detected")
        return {
            **state,
            "current_stage": "STAGE_1_ANALYZE",
            "security_result": security_result,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    # Guideline compliance review
    guidelines = ["PEP8", "Type hinting", "Docstrings"]
    review_result = review_agent.execute(diff_output, guidelines)

    if review_result.get("status") == "APPROVED":
        logger.success("Stage 5 Complete — Zero violations detected")
        return {
            **state,
            "current_stage": "STAGE_5_REVIEW",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "security_result": security_result,
            "review_result": review_result,
        }
    else:
        logger.warning("Stage 5 Failed — Guideline compliance issues")
        return {
            **state,
            "current_stage": "STAGE_1_ANALYZE",
            "security_result": security_result,
            "review_result": review_result,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }


def stage_6_publish(state: ResolvState) -> ResolvState:
    """
    Stage 6: Publish — Commit, push, and open Pull Request (ready-for-review).
    """
    logger = _get_logger(state)
    logger.info("Stage 6: Publish — Committing changes and opening Pull Request...")

    project_config = state.get("project_config", {})
    patch_modified_files = state.get("modified_files", [])
    worktree_path = state.get("worktree_path", "./")
    branch_name = state.get("branch_name") or f"resolv/{state.get('issue_id', 'unknown')}"

    logger.debug(f"project_config keys={list(project_config.keys()) if isinstance(project_config, dict) else type(project_config)}")
    logger.debug(f"patch_modified_files={patch_modified_files}")
    logger.debug(f"worktree_path={worktree_path}")
    logger.debug(f"branch_name={branch_name}")
    logger.debug(f"worktree_exists={Path(worktree_path).exists()}")
    logger.debug(f"diff_output length={len(state.get('diff_output', '') or '')}")
    logger.debug(f"credentials_store present={bool(state.get('credentials_store'))}")

    from agents.tools.remote_git import RemoteGitSubAgent
    remote_agent = RemoteGitSubAgent(logger, project_config)

    # Validate worktree exists before committing/pushing
    if not Path(worktree_path).exists():
        logger.error(f"Worktree directory not found: {worktree_path}")
        raise FileNotFoundError(
            f"Worktree directory not found: {worktree_path}. "
            "Stage 3 may have failed to create the worktree, or it was cleaned up prematurely."
        )

    # Determine what was planned vs what was actually applied
    applied, planned_files, applied_files = _planned_changes_applied(state)

    # If nothing was planned, this is a no-op — complete gracefully without PR
    if not planned_files:
        logger.warning("No code changes were planned — Stage 6 is a no-op, skipping publish")
        return {
            **state,
            "current_stage": "STAGE_6_PUBLISH",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "pr_url": None,
            "pr_draft": False,
            "branch_name": branch_name,
        }

    # If changes were planned but not applied — fail fast
    if not applied:
        logger.error(
            f"Changes were planned for {planned_files} but none were applied. "
            "Stage 3 did not implement the planned changes."
        )
        raise RuntimeError(
            f"Stage 6 failed: planned changes for {planned_files} were not applied by Stage 3. "
            "The coding agent must implement the planned file changes before publishing."
        )

    diff_output = state.get("diff_output", "") or ""
    if not diff_output.strip():
        logger.error("No diff output to publish — Stage 3 produced no actual changes")
        raise RuntimeError(
            "Stage 6 failed: diff output is empty. Stage 3 did not synthesize any code changes."
        )

    # Resolve repo_full_name from state
    repo_full_name = state.get("repo_full_name")

    # Commit changes
    commit_msg = f"fix: auto-resolved issue via Resolv [{state.get('issue_id', 'unknown')}]"
    remote_agent.commit_changes(worktree_path, patch_modified_files, commit_msg)

    # Push branch (best-effort; worktree may have no changes)
    remote_agent.push_branch(worktree_path, "origin", branch_name)

    # Resolve credentials from the session file directly (source of truth)
    from config.models import load_credentials
    
    session_path = Path(state["session_path"])
    cred_store = load_credentials(str(session_path))

    # Open Pull Request (ready-for-review, not draft)
    from agents.tools.github_platform import GitHubPlatformSubAgent
    platform_agent = GitHubPlatformSubAgent(logger, project_config)
    
    # Resolve primary repo full name
    primary = {}
    if isinstance(project_config, dict):
        repos = project_config.get("repos", {})
        primary = repos.get("primary", {})
    
    repo_full_name = None
    if isinstance(primary, dict):
        base = primary.get("base")
        path = primary.get("path")
        if base == "github.com" and path:
            repo_full_name = path

    # Pre-flight credential validation
    platform_agent._authenticate(credential_store=cred_store)
    if not platform_agent.validate_credentials(repo_full_name=repo_full_name):
        logger.error("GitHub credential validation failed. Cannot proceed with publishing.")
        raise RuntimeError("GitHub authentication failed. Please check your GitHub token and repository access permissions.")


    # Generate PR summary
    diff_output = state.get("diff_output", "")
    test_results = state.get("test_results", {})
    pr_summary = platform_agent.generate_pr_summary(diff_output, test_results)



    pr_url = platform_agent.open_pull_request(
        title=pr_summary.get("title", f"fix: auto-resolved issue [{state.get('issue_id', 'unknown')}]"),
        body=pr_summary.get("body", ""),
        head=branch_name,
        base="main",
        draft=False,
        repo_full_name=repo_full_name,
    )

    logger.success(f"Stage 6 Complete — Pull Request opened: {pr_url}")

    return {
        **state,
        "current_stage": "STAGE_6_PUBLISH",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "pr_url": pr_url,
        "pr_draft": False,
        "branch_name": branch_name,
    }


def stage_7_record(state: ResolvState) -> ResolvState:
    """
    Stage 7: Record — Finalize persistence, audit log, Langfuse telemetry.
    """
    logger = _get_logger(state)
    logger.info("Stage 7: Record — Finalizing session telemetry...")

    session_path = Path(state["session_path"])
    audit_path = session_path / "audit.log"

    # Build audit entry
    import hashlib
    import json as _json

    audit_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": state.get("session_id"),
        "issue_reference": state.get("issue_reference"),
        "final_stage": state.get("current_stage"),
        "status": "COMPLETED",
        "pr_url": state.get("pr_url"),
        "modified_files": state.get("modified_files", []),
        "healing_turns": state.get("healing_turns", 0),
        "token_usage": state.get("token_usage"),
        "cost_estimate": state.get("cost_estimate"),
    }

    # Hash-chain: compute hash of this entry + previous hash
    previous_hash = ""
    if audit_path.exists():
        with open(audit_path, "r") as f:
            lines = f.readlines()
            if lines:
                last_entry = _json.loads(lines[-1])
                previous_hash = last_entry.get("hash", "")

    entry_data = _json.dumps(audit_entry, sort_keys=True, default=str)
    data_hash = hashlib.sha256((previous_hash + entry_data).encode()).hexdigest()
    audit_entry["hash"] = data_hash
    audit_entry["previous_hash"] = previous_hash

    # Write audit.log (plain text, ANSI stripped)
    with open(audit_path, "a", encoding="utf-8") as f:
        f.write(_json.dumps(audit_entry, default=str) + "\n")

    # Export to Langfuse
    from agents.tools.langfuse_exporter import LangfuseExporterSubAgent
    langfuse_agent = LangfuseExporterSubAgent(logger, state.get("global_config", {}))
    trace_id = langfuse_agent.flush_trace(
        session_id=state.get("session_id", ""),
        stage=state.get("current_stage", ""),
        metrics=state.get("token_usage", {}),
    )

    logger.success(f"Stage 7 Complete — Audit log written to {audit_path}")

    return {
        **state,
        "current_stage": "STAGE_7_RECORD",
        "status": "COMPLETED",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "audit_log_path": str(audit_path),
        "langfuse_trace_id": trace_id,
    }


# =============================================================================
# Conditional Edge Router
# =============================================================================

def route_after_stage_4(state: ResolvState) -> str:
    """After Stage 4: if tests passed, go to Stage 5; if failed with turns remaining, back to Stage 3; else Stage 6."""
    if state.get("test_results", {}).get("returncode") == 0:
        return "stage_5_review"
    healing = state.get("healing_turns", 0)
    max_healing = state.get("max_healing_turns", 3)
    if healing < max_healing:
        return "stage_3_apply"
    return "stage_6_publish"


def route_after_stage_5(state: ResolvState) -> str:
    """After Stage 5: if approved, go to Stage 6; if failed, back to Stage 1/2."""
    review = state.get("review_result", {})
    if review.get("status") == "APPROVED":
        return "stage_6_publish"
    route_back = review.get("route_back_to", "stage_1_analyze")
    return route_back


# =============================================================================
# Build the StateGraph
# =============================================================================

def build_graph(checkpointer=None) -> StateGraph:
    """
    Build the LangGraph StateGraph with all 7 stages and conditional edges.
    """
    workflow = StateGraph(ResolvState)

    # Add nodes
    workflow.add_node("stage_0_setup", stage_0_setup)
    workflow.add_node("stage_1_analyze", stage_1_analyze)
    workflow.add_node("stage_2_plan", stage_2_plan)
    workflow.add_node("stage_3_apply", stage_3_apply)
    workflow.add_node("stage_4_build_test", stage_4_build_test)
    workflow.add_node("stage_5_review", stage_5_review)
    workflow.add_node("stage_6_publish", stage_6_publish)
    workflow.add_node("stage_7_record", stage_7_record)

    # Set entry point
    workflow.set_entry_point("stage_0_setup")

    # Linear edges
    workflow.add_edge("stage_0_setup", "stage_1_analyze")
    workflow.add_edge("stage_1_analyze", "stage_2_plan")
    workflow.add_edge("stage_2_plan", "stage_3_apply")
    workflow.add_edge("stage_3_apply", "stage_4_build_test")

    # Conditional edges from Stage 4
    workflow.add_conditional_edges(
        "stage_4_build_test",
        route_after_stage_4,
        {
            "stage_3_apply": "stage_3_apply",
            "stage_5_review": "stage_5_review",
            "stage_6_publish": "stage_6_publish",
        },
    )

    # Conditional edges from Stage 5
    workflow.add_conditional_edges(
        "stage_5_review",
        route_after_stage_5,
        {
            "stage_1_analyze": "stage_1_analyze",
            "stage_2_plan": "stage_2_plan",
            "stage_6_publish": "stage_6_publish",
        },
    )

    # Linear edges
    workflow.add_edge("stage_6_publish", "stage_7_record")
    workflow.add_edge("stage_7_record", END)

    # Compile with checkpointer
    if checkpointer is None:
        checkpointer = MemorySaver()

    return workflow.compile(checkpointer=checkpointer)


# =============================================================================
# Resume Support
# =============================================================================

def load_state_from_checkpoint(session_path: str) -> Optional[ResolvState]:
    """Load state from metadata.json for --resume support."""
    metadata_path = os.path.join(session_path, "metadata.json")
    if not os.path.exists(metadata_path):
        return None
    with open(metadata_path, "r") as f:
        metadata = json.load(f)
    return metadata
