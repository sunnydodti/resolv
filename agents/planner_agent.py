from pydantic import BaseModel
from agents.base import BaseAgent
from core.logger import ResolvLogger
from typing import List, Dict, Any
from pathlib import Path
import re


class PlanStep(BaseModel):
    step_id: int
    action: str
    target_file: str
    description: str
    estimated_tokens: int


class PlannerAgent(BaseAgent):
    """
    Formulates step-by-step resolution roadmaps while enforcing resource limits.
    Generates one plan step per affected source file discovered in context.
    """

    def __init__(self, logger: ResolvLogger, config):
        super().__init__(logger, config)
        self.token_budget = 10000

    def execute(self, context: dict) -> List[PlanStep]:
        """Synthesize context into an actionable plan."""
        self.logger.info("Generating resolution roadmap...")

        issue = context.get("issue", "unknown")
        symbols: list = context.get("symbols", [])
        source_files: list = context.get("source_files", [])
        grep_matches: dict = context.get("grep_matches", {})
        repo_root: str = context.get("repo_root", "")

        def _to_rel(abs_path: str) -> str:
            """Convert an absolute path to a path relative to repo_root."""
            if not repo_root:
                return abs_path
            try:
                return str(Path(abs_path).resolve().relative_to(Path(repo_root).resolve()))
            except ValueError:
                return abs_path

        plan: List[PlanStep] = []
        step_id = 1

        # Determine which files are relevant based on grep matches
        relevant_files: set = set()
        if grep_matches:
            # Grep match format: "absolute_path:line:content"
            # Use regex to extract the path (everything before :<digits>:)
            path_re = re.compile(r"^(.*?):(\d+):(.*)$")
            for _path, matches in grep_matches.items():
                for match in matches:
                    m = path_re.match(match)
                    if m:
                        file_part = m.group(1)
                        if file_part:
                            relevant_files.add(_to_rel(file_part))
            self.logger.debug(f"Relevant files from grep matches: {sorted(relevant_files)}")

        # If we have grep matches, plan edits for those files
        if relevant_files:
            for file_path in sorted(relevant_files):
                rel_path = file_path
                self.logger.debug(f"Planning edit step for grep-relevant file: {rel_path}")
                plan.append(PlanStep(
                    step_id=step_id,
                    action="edit_file",
                    target_file=rel_path,
                    description=f"Apply issue-related changes to {rel_path}",
                    estimated_tokens=1500,
                ))
                step_id += 1

        # Fallback: if no grep matches but we have source files with symbols, plan for those
        elif source_files:
            # Prioritize files that had symbols parsed
            files_with_symbols = {
                s.get("file", "") for s in symbols
                if s.get("functions") or s.get("classes")
            }
            target_files = sorted(files_with_symbols) if files_with_symbols else sorted(source_files)
            for file_path in target_files:
                rel_path = _to_rel(file_path)
                self.logger.debug(f"Planning edit step for symbol-bearing file: {rel_path}")
                plan.append(PlanStep(
                    step_id=step_id,
                    action="edit_file",
                    target_file=rel_path,
                    description=f"Apply issue-related changes to {rel_path}",
                    estimated_tokens=1500,
                ))
                step_id += 1

        # Last-resort fallback: single generic step targeting the issue reference
        if not plan:
            self.logger.warning(
                f"No source files or grep matches found for issue '{issue}'; "
                "generating generic analyze step"
            )
            plan.append(PlanStep(
                step_id=1,
                action="analyze_symbols",
                target_file=issue,
                description="Analyze issue-related code symbols",
                estimated_tokens=1000,
            ))

        self.logger.info(f"Plan generated with {len(plan)} steps")
        for step in plan:
            self.logger.debug(f"  step {step.step_id}: {step.action} -> {step.target_file} ({step.description})")
        self.logger.success(f"Plan generated with {len(plan)} steps")
        return plan