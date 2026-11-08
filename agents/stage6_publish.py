from agents.tools.remote_git import RemoteGitSubAgent
from core.logger import ResolvLogger
from config.models import load_global_config

COMMIT_MESSAGE_TEMPLATE = '{type}({scope}): {description}\n\n{body}\n\nCloses: #{issue_id}'

LLM_COMMIT_PROMPT = """Generate a conventional commit message with these constraints:
- Subject: max 50 characters, format type(scope): description
- Body: max 72 characters per line
- Footer: Closes: #{issue_id}"""

def run_stage_6(logger: ResolvLogger, patch_result, project_config, state=None):
    """Stage 6: Publish — Commit, push, and open Pull Request."""
    logger.info("Stage 6: Publish — Committing changes and opening PR...")
def run_stage_6(logger: ResolvLogger, patch_result, project_config):
    """Stage 6: Publish — Commit, push, and open Pull Request."""
    logger.info("Stage 6: Publish — Committing changes and opening PR...")
    
    config = load_global_config()
    remote_agent = RemoteGitSubAgent(logger, config)
    
    primary_repo = project_config.repos.primary.repopath if hasattr(project_config, 'repos') else "./"
    branch = "resolv/auto-fix"
    
    # Commit changes
    remote_agent.logger = logger
    remote_agent.commit_changes(primary_repo, patch_result.modified_files, "fix: auto-resolved issue via Resolv")
    
    # Push branch
    remote_agent.push_branch(primary_repo, "origin", branch)
    
    logger.success(f"Stage 6 Complete — Branch {branch} published")
    return {"branch": branch, "status": "PUBLISHED"}
