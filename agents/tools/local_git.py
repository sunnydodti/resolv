import os
import subprocess
import shutil
import uuid
import traceback
from pathlib import Path
from typing import List
from agents.base import SubAgent
from core.logger import ResolvLogger


def _norm_path(p: str | Path) -> str:
    """Normalize a path for cross-platform comparison (handles slash/backslash differences on Windows)."""
    return os.path.normpath(str(Path(p)))


class LocalGitSubAgent(SubAgent):
    """
    Handles deterministic Git workspace management.
    Operations: InitSessionWorkspace, PrepareBranches, CreateWorktree, CommitChanges, ComputeDiff.
    """

    def __init__(self, logger: ResolvLogger, config):
        super().__init__(logger, config)
        self.worktree_root = Path(".resolv/worktrees")

    def _git_dir_args(self, repo_path: Path) -> List[str]:
        """Build --git-dir and --work-tree args to avoid cwd permission issues on Windows."""
        return [
            "git",
            "--git-dir", str(repo_path / ".git"),
            "--work-tree", str(repo_path),
        ]

    def _run_git(self, args: List[str], repo_path: Path | None = None,
                 operation: str = "git") -> subprocess.CompletedProcess:
        """Run a git command, optionally scoped to a repo via --git-dir/--work-tree.

        Using --git-dir/--work-tree instead of cwd avoids Windows PermissionError
        when the directory has restrictive ACLs that prevent subprocess from using
        it as a working directory.
        """
        full_args = args
        if repo_path is not None:
            full_args = self._git_dir_args(repo_path) + args[1:] if args[0] == "git" else args
        try:
            return subprocess.run(
                full_args,
                check=True,
                capture_output=True,
                text=True,
            )
        except PermissionError as e:
            self.logger.error(
                f"Permission denied running '{operation}' on {repo_path}. "
                f"Ensure the directory is accessible and not locked by another process."
            )
            raise
        except OSError as e:
            self.logger.error(
                f"OS error running '{operation}' on {repo_path}: {e}"
            )
            raise

    def _worktree_exists(self, worktree_path: Path) -> bool:
        """Check if a git worktree already exists at the given path."""
        if not worktree_path.exists():
            return False
        git_dir = worktree_path / ".git"
        if git_dir.exists():
            return True
        try:
            result = self._run_git(
                ["git", "rev-parse", "--git-dir"],
                repo_path=worktree_path,
                operation="rev-parse --git-dir",
            )
            return result.returncode == 0
        except (subprocess.CalledProcessError, PermissionError, OSError):
            return False

    def _list_existing_worktrees(self, repo_path: Path) -> List[str]:
        """List all existing worktree paths for a repository."""
        try:
            result = self._run_git(
                ["git", "worktree", "list", "--porcelain"],
                repo_path=repo_path,
                operation="worktree list",
            )
            worktrees = []
            for line in result.stdout.splitlines():
                if line.startswith("worktree "):
                    worktrees.append(_norm_path(line[len("worktree "):]))
            return worktrees
        except (subprocess.CalledProcessError, PermissionError, OSError):
            return []

    def _cleanup_old_worktrees(self, repo_path: Path, keep: List[str]) -> None:
        """Remove old worktrees that are no longer needed."""
        existing = self._list_existing_worktrees(repo_path)
        keep_set = {_norm_path(k) for k in keep}
        repo_path_norm = _norm_path(repo_path)
        for wt_path in existing:
            if wt_path not in keep_set and wt_path != repo_path_norm:
                try:
                    self._run_git(
                        ["git", "worktree", "remove", "--force", wt_path],
                        repo_path=repo_path,
                        operation="worktree remove",
                    )
                    self.logger.info(f"Cleaned up old worktree: {wt_path}")
                except subprocess.CalledProcessError as e:
                    self.logger.warning(
                        f"Could not remove old worktree {wt_path}: {e.stderr.strip()}"
                    )

    def init_session_workspace(self, repo_path: str, feature_branch: str) -> str:
        """Create isolated feature branch and worktree.

        If a worktree already exists for this session, it is synced (pulled)
        and reused. Otherwise a new worktree is created from the repo.
        Old worktrees are cleaned up after creating the new one.
        """
        self.logger.info(f"Creating worktree for {repo_path}")

        try:
            return self._init_session_workspace_impl(repo_path, feature_branch)
        except PermissionError as e:
            self.logger.error(
                f"Permission denied initializing workspace for {repo_path}: {e}"
            )
            self.logger.debug(traceback.format_exc())
            raise

    def _init_session_workspace_impl(self, repo_path: str, feature_branch: str) -> str:
        """Internal implementation of init_session_workspace."""
        repo = Path(repo_path)
        if not repo.exists():
            self.logger.error(f"Repository not found: {repo_path}")
            raise FileNotFoundError(repo_path)

        self.worktree_root.mkdir(parents=True, exist_ok=True)

        # Unique worktree path per session — absolute path relative to repo
        worktree_path = repo / self.worktree_root / feature_branch

        # If worktree already exists, sync it instead of re-creating
        if self._worktree_exists(worktree_path):
            self.logger.info(f"Worktree already exists at {worktree_path}, syncing...")
            try:
                self._run_git(
                    ["git", "worktree", "unlock", str(worktree_path)],
                    repo_path=repo,
                    operation="worktree unlock",
                )
            except subprocess.CalledProcessError:
                pass  # May not be locked
            try:
                self._run_git(
                    ["git", "pull", "--ff-only"],
                    repo_path=worktree_path,
                    operation="pull --ff-only",
                )
                self.logger.info(f"Worktree synced: {worktree_path}")
            except subprocess.CalledProcessError as e:
                self.logger.warning(
                    f"Worktree sync failed (may have local changes): {e.stderr.strip()}"
                )
        else:
            # Create feature branch in the main repo if it doesn't exist
            try:
                self._run_git(
                    ["git", "rev-parse", "--verify", feature_branch],
                    repo_path=repo,
                    operation="rev-parse --verify",
                )
                self.logger.debug(f"Feature branch already exists: {feature_branch}")
            except subprocess.CalledProcessError:
                self._run_git(
                    ["git", "checkout", "-b", feature_branch],
                    repo_path=repo,
                    operation="checkout -b",
                )
                self.logger.debug(f"Created feature branch: {feature_branch}")

            # Create git worktree from the feature branch
            # Remove any existing worktree directory first
            if worktree_path.exists():
                shutil.rmtree(worktree_path, ignore_errors=True)
                self.logger.info(f"Removed existing worktree directory: {worktree_path}")
            # Use a unique branch name to avoid conflicts with existing worktrees
            unique_branch = f"{feature_branch}-{uuid.uuid4().hex[:8]}"
            # Use git worktree add -b to create branch and worktree in one command
            self._run_git(
                ["git", "worktree", "add", str(worktree_path), "-b", unique_branch],
                repo_path=repo,
                operation="worktree add",
            )
            self.logger.success(f"Worktree created at: {worktree_path}")

        # Cleanup old worktrees (keep the current one and the main repo)
        existing = self._list_existing_worktrees(repo)
        self._cleanup_old_worktrees(repo, [str(worktree_path), str(repo)])

        return str(worktree_path)

    def commit_changes(self, repo_path: str, files: List[str], message: str):
        """Commit changes in the worktree."""
        self.logger.info(f"Committing changes: {message}")
        try:
            subprocess.run(
                ["git", "add"] + files,
                cwd=str(repo_path),
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "commit", "-m", message],
                cwd=str(repo_path),
                check=True,
                capture_output=True,
            )
            self.logger.success("Commit successful")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Commit failed: {e.stderr.decode()}")
            raise e
        except PermissionError as e:
            self.logger.error(
                f"Permission denied committing changes in {repo_path}: {e}"
            )
            raise

    def compute_diff(self, repo_path: str) -> str:
        """Compute the unified diff of the current worktree."""
        self.logger.debug("Computing diff...")
        try:
            result = subprocess.run(
                ["git", "--git-dir", str(Path(repo_path) / ".git"), "--work-tree", str(repo_path), "diff", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout
        except subprocess.CalledProcessError:
            # Diff may be empty (no staged changes) or git diff --cached
            # not supported with --git-dir/--work-tree; return empty diff
            return ""
        except PermissionError as e:
            self.logger.error(
                f"Permission denied computing diff in {repo_path}: {e}"
            )
            raise

