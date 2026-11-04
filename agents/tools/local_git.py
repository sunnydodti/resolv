import os
import subprocess
from pathlib import Path
from typing import List
from agents.base import SubAgent
from core.logger import ResolvLogger

class LocalGitSubAgent(SubAgent):
    """
    Handles deterministic Git workspace management.
    Operations: InitSessionWorkspace, PrepareBranches, CreateWorktree, CommitChanges, ComputeDiff.
    """
    def __init__(self, logger: ResolvLogger, config):
        super().__init__(logger, config)
        self.worktree_root = Path(".resolv/worktrees")

    def init_session_workspace(self, repo_path: str, feature_branch: str) -> str:
        """Create isolated feature branch and worktree."""
        self.logger.info(f"Creating worktree for {repo_path}")
        
        repo = Path(repo_path)
        if not repo.exists():
            self.logger.error(f"Repository not found: {repo_path}")
            raise FileNotFoundError(repo_path)

        self.worktree_root.mkdir(parents=True, exist_ok=True)
        worktree_path = self.worktree_root / feature_branch

        try:
            # Create feature branch
            subprocess.run(
                ["git", "checkout", "-b", feature_branch],
                cwd=repo,
                check=True,
                capture_output=True
            )
            self.logger.debug(f"Created feature branch: {feature_branch}")

            # Create git worktree
            subprocess.run(
                ["git", "worktree", "add", str(worktree_path), feature_branch],
                cwd=repo,
                check=True,
                capture_output=True
            )
            self.logger.success(f"Worktree created at: {worktree_path}")
            return str(worktree_path)
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Git command failed: {e.stderr.decode()}")
            raise e

    def commit_changes(self, repo_path: str, files: List[str], message: str):
        """Commit changes in the worktree."""
        self.logger.info(f"Committing changes: {message}")
        try:
            subprocess.run(["git", "add"] + files, cwd=repo_path, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", message], cwd=repo_path, check=True, capture_output=True)
            self.logger.success("Commit successful")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Commit failed: {e.stderr.decode()}")
            raise e

    def compute_diff(self, repo_path: str) -> str:
        """Compute the unified diff of the current worktree."""
        self.logger.debug("Computing diff...")
        try:
            result = subprocess.run(
                ["git", "diff", "--cached"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Diff failed: {e.stderr.decode()}")
            raise e
