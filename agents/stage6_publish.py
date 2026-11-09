from agents.tools.remote_git import RemoteGitSubAgent
from core.logger import ResolvLogger
from config.models import load_global_config

def run_stage_6(logger: ResolvLogger, patch_result, project_config, state):
    """Stage 6: Publish — Commit, push, and open Pull Request."""
    logger.info("Stage 6: Publish — Committing changes and opening PR...")
    
    config = load_global_config()
    remote_agent = RemoteGitSubAgent(logger, config)
    
    primary_repo = project_config.repos.primary.repopath if hasattr(project_config, 'repos') else "./"
    branch = f"resolv/{state.get('issue_id', 'auto-fix')}"
    
    # Commit changes
    issue_id = state.get('issue_id', 'unknown')
    remote_agent.logger = logger
    remote_agent.commit_changes(
        primary_repo, 
        patch_result.modified_files, 
        type="fix", 
        scope="resolv", 
        description="auto-resolved issue",
        footer=f"Closes: #{issue_id}"
    )
    
    # Push branch
    remote_agent.push_branch(primary_repo, "origin", branch)
    
    logger.success(f"Stage 6 Complete — Branch {branch} published")
    return {"branch": branch, "status": "PUBLISHED"}
