"""
DiffFallbackSubAgent — Deterministic agent for applying git diff fallbacks.
Operation: ApplyGitDiffFallback.
"""
import subprocess
from pathlib import Path

from agents.base import SubAgent
from core.logger import ResolvLogger


class DiffFallbackSubAgent(SubAgent):
    """Applies git diff as a fallback when structured edits fail."""

    def __init__(self, logger: ResolvLogger, config):
        super().__init__(logger, config)

    def apply_git_diff_fallback(self, repo_path: str, diff_content: str) -> bool:
        """Apply a unified diff to the repository."""
        self.logger.info("Applying git diff fallback...")
        try:
            # Write diff to temp file
            diff_file = Path(repo_path) / ".resolv_fallback.diff"
            diff_file.write_text(diff_content)

            # Apply using git apply
            result = subprocess.run(
                ["git", "apply", str(diff_file)],
                cwd=repo_path,
                capture_output=True,
                text=True,
            )

            # Clean up
            diff_file.unlink(missing_ok=True)

            if result.returncode == 0:
                self.logger.success("Git diff fallback applied successfully")
                return True
            else:
                self.logger.error(f"Git diff fallback failed: {result.stderr}")
                return False
        except Exception as e:
            self.logger.error(f"Git diff fallback error: {e}")
            return False
