from pathlib import Path
import subprocess
from typing import List
from agents.base import SubAgent
from core.logger import ResolvLogger

class RemoteGitSubAgent(SubAgent):
    """
    Handles remote repository interactions.
    Operations: ResolveRepoPath, PushBranch, AuthTransport, CloneRepo.
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

    def clone_repo(self, repo_url: str, target_path: str) -> str:
        """Clone a remote repository to the local target path.

        Returns the target path on success.
        FAIL EARLY if clone fails.
        """
        target = Path(target_path)
        if target.exists():
            self.logger.info(f"Repository already exists at {target_path}, skipping clone")
            return str(target)

        target.parent.mkdir(parents=True, exist_ok=True)

        self.logger.info(f"Cloning {repo_url} -> {target_path}")
        try:
            result = subprocess.run(
                ["git", "clone", repo_url, str(target)],
                check=True,
                capture_output=True,
                text=True,
            )
            self.logger.success(f"Repository cloned to {target_path}")
            return str(target)
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Git clone failed: {e.stderr}")
            raise RuntimeError(f"Failed to clone {repo_url}: {e.stderr}")

    def push_branch(self, repo_path: str, remote: str, branch: str):
        """Push local feature branch to remote repository.

        Uses `git --git-dir <repo>/.git --work-tree <repo> push` because
        git worktrees store .git as a file, and `git -C` requires the
        directory to exist with correct permissions on Windows.
        """
        self.logger.info(f"Pushing branch {branch} to {remote}...")
        repo = Path(repo_path)
        if not repo.exists():
            self.logger.warning(f"Worktree directory not found: {repo_path}")
            self.logger.warning("Skipping push - worktree directory missing")
            return
        try:
            subprocess.run(
                ["git", "--git-dir", str(repo / ".git"), "--work-tree", str(repo), "push", remote, f"HEAD:{branch}"],
                check=True,
                capture_output=True,
                text=True,
            )
            self.logger.success(f"Branch {branch} pushed successfully")
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode() if isinstance(e.stderr, bytes) else (e.stderr or "")
            if "did not match any" in stderr or "remote" in stderr.lower() or "not a git repository" in stderr.lower():
                self.logger.warning(
                    f"Push failed: remote '{remote}' may not be configured. "
                    f"Add it with: git -C {repo_path} remote add origin <url>"
                )
            else:
                self.logger.error(f"Push failed: {stderr}")
            raise e

    def commit_changes(self, repo_path: str, files: List[str], type: str, scope: str, description: str, body: str = "", footer: str = ""):
        """Commit changes using Conventional Commits format.

        Uses `git -C <repo_path>` instead of --git-dir/--work-tree because
        git worktrees store .git as a file, and --git-dir pointing to that
        file does not resolve correctly on Windows.
        """
        message = f"{type}({scope}): {description}"
        if body:
            message += f"\n\n{body}"
        if footer:
            message += f"\n\n{footer}"

        self.logger.info(f"Committing {len(files)} file(s): {message}")
        repo = Path(repo_path)
        if not repo.exists():
            self.logger.error(f"Repository directory not found: {repo_path}")
            raise FileNotFoundError(f"Repository directory not found: {repo_path}")
        # Filter to existing files only
        existing_files = [f for f in files if (repo / f).exists()]
        if not existing_files:
            self.logger.warning("No files to commit, skipping commit")
            return
        try:
            subprocess.run(
                ["git", "-C", str(repo_path), "add"] + existing_files,
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "-C", str(repo_path), "commit", "-m", message],
                check=True,
                capture_output=True,
                text=True,
            )
            self.logger.success("Commit successful")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Commit failed: {e.stderr}")
            raise e
