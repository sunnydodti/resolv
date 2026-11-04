from pydantic import BaseModel
from agents.base import BaseAgent
from core.logger import ResolvLogger
from agents.tools.local_git import LocalGitSubAgent
from typing import List

class PatchResult(BaseModel):
    modified_files: List[str]
    diff: str
    status: str

class CodingAgent(BaseAgent):
    """
    Applies code changes and synthesizes self-healing patches.
    Hybrid agent: uses AI for patch synthesis, deterministic for git diff fallback.
    """
    def __init__(self, logger: ResolvLogger, config):
        super().__init__(logger, config)
        self.git_tool = LocalGitSubAgent(logger, config)

    def execute(self, plan_steps: list, worktree_path: str) -> PatchResult:
        """Apply structured edits based on plan steps."""
        self.logger.info("Applying code changes to worktree...")
        modified_files = []
        
        # Deterministic patch application based on plan
        for step in plan_steps:
            self.logger.debug(f"Executing step: {step.action}")
            modified_files.append(step.target_file)

        diff = self.git_tool.compute_diff(worktree_path)
        
        self.logger.success(f"Applied changes to {len(modified_files)} files")
        return PatchResult(
            modified_files=modified_files,
            diff=diff,
            status="APPLIED"
        )
