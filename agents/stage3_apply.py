from agents.coding_agent import CodingAgent
from core.logger import ResolvLogger
from config.models import load_global_config
from pathlib import Path

def run_stage_3(logger: ResolvLogger, plan_steps: list, project_config):
    """Stage 3: Apply — Create isolated worktrees and synthesize code edits."""
    logger.info("Stage 3: Apply — Synthesizing structured code edits in worktree...")
    
    config = load_global_config()
    coding_agent = CodingAgent(logger, config)
    
    # Resolve primary repo path from config
    primary_repo = project_config.repos.primary.repopath if hasattr(project_config, 'repos') else "./"
    feature_branch = "resolv/auto-fix"
    
    # Create worktree using LocalGitSubAgent
    worktree_path = coding_agent.git_tool.init_session_workspace(primary_repo, feature_branch)
    
    # Apply planned edits
    patch_result = coding_agent.execute(plan_steps, worktree_path)
    
    logger.success(f"Stage 3 Complete — {len(patch_result.modified_files)} file(s) modified")
    return patch_result
