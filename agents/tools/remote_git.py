from pathlib import Path
from agents.base import SubAgent
from core.logger import ResolvLogger

class RemoteGitSubAgent(SubAgent):
    """
    Handles remote repository interactions.
    Operations: ResolveRepoPath, PushBranch, AuthTransport.
    """
    def __init__(self, logger: ResolvLogger, config):
        super().__init__(logger, config)
        self.remote_urls = {}

    def resolve_repo_path(self, source_url: str) -> str:
        """Resolve remote source URL to local repository path."""
        self.logger.info(f"Resolving repo path for: {source_url}")
        # Simple mapping logic based on source URL
        repo_name = source_url.split('/')[-1].replace('.git', '')
        path = f"./{repo_name}"
        self.remote_urls[source_url] = path
        self.logger.success(f"Resolved path: {path}")
        return path

    def push_branch(self, repo_path: str, remote: str, branch: str):
        """Push local feature branch to remote repository."""
        self.logger.info(f"Pushing branch {branch} to {remote}...")
        try:
            import subprocess
            subprocess.run(
                ["git", "push", remote, branch],
                cwd=repo_path,
                check=True,
                capture_output=True
            )
            self.logger.success(f"Branch {branch} pushed successfully")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Push failed: {e.stderr.decode()}")
            raise e
