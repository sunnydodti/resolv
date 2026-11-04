"""
GitHistorySubAgent — Deterministic agent for Git history operations.
Operations: GitLog, GitBlame.
"""
import subprocess
from typing import List, Optional

from agents.base import SubAgent
from core.logger import ResolvLogger


class GitHistorySubAgent(SubAgent):
    """Handles Git history exploration."""

    def __init__(self, logger: ResolvLogger, config):
        super().__init__(logger, config)

    def git_log(self, repo_path: str, max_count: int = 20) -> List[dict]:
        """Get recent commit history."""
        self.logger.debug(f"GitLog: {repo_path} (max {max_count} commits)")
        try:
            result = subprocess.run(
                ["git", "log", f"-{max_count}", "--pretty=format:%H|%s|%an|%ad", "--date=short"],
                cwd=repo_path, capture_output=True, text=True, check=True
            )
            commits = []
            for line in result.stdout.strip().split("\n"):
                if line:
                    parts = line.split("|")
                    commits.append({
                        "hash": parts[0] if len(parts) > 0 else "",
                        "subject": parts[1] if len(parts) > 1 else "",
                        "author": parts[2] if len(parts) > 2 else "",
                        "date": parts[3] if len(parts) > 3 else "",
                    })
            return commits
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Git log failed: {e.stderr.decode()}")
            return []

    def git_blame(self, repo_path: str, file_path: str, line_number: Optional[int] = None) -> dict:
        """Get blame information for a file or specific line."""
        self.logger.debug(f"GitBlame: {file_path}:{line_number}")
        try:
            cmd = ["git", "blame", "--porcelain", file_path]
            if line_number:
                cmd.extend(["-L", f"{line_number},{line_number}"])
            result = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True, check=True)
            return {"blame": result.stdout, "file": file_path, "line": line_number}
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Git blame failed: {e.stderr.decode()}")
            return {"blame": "", "file": file_path, "line": line_number, "error": e.stderr.decode()}
