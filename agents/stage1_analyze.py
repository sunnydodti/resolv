from agents.context_agent import ContextAgent
from core.logger import ResolvLogger
from config.models import load_global_config, get_resolv_dir
import json
from pathlib import Path

def run_stage_1(logger: ResolvLogger, issue_reference: str, project_config):
    """Stage 1: Analyze — Context gathering and semantic exploration."""
    logger.info("Stage 1: Analyze — Ingesting issue and exploring codebase...")
    
    config = load_global_config()
    context_agent = ContextAgent(logger, config)
    
    # Extract repo paths from project config
    repo_paths = []
    if hasattr(project_config, 'repos'):
        for repo_key, repo_cfg in project_config.repos.items():
            repo_paths.append(repo_cfg.repopath)
    
    context_result = context_agent.execute(issue_reference, repo_paths)
    
    # Save dual-representation artifacts under Resolv home
    session_path = Path(get_resolv_dir() / "sessions" / "temp")
    session_path.mkdir(parents=True, exist_ok=True)
    
    with open(session_path / "context.json", "w") as f:
        json.dump(context_result, f, indent=2)
    
    logger.success("Stage 1 Complete — Generated context.json & analysis.md")
    return context_result
