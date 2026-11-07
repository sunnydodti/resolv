from pydantic import BaseModel
from agents.base import BaseAgent
from core.logger import ResolvLogger
from typing import List, Dict, Any
from pathlib import Path
import re
import json


class PlanStep(BaseModel):
    step_id: int
    action: str
    target_file: str
    description: str
    estimated_tokens: int


class PlannerAgent(BaseAgent):
    """
    Formulates step-by-step resolution roadmaps while enforcing resource limits.
    Uses the LLM gateway to analyze the issue and context, then generates
    specific, actionable plan steps for each affected source file.
    """

    def __init__(self, logger: ResolvLogger, config, llm_gateway=None):
        super().__init__(logger, config)
        self.token_budget = 10000
        self.llm_gateway = llm_gateway

    def execute(self, context: dict) -> List[PlanStep]:
        """Synthesize context into an actionable plan using the LLM."""
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

        # Determine which files are relevant based on grep matches
        relevant_files: set = set()
        if grep_matches:
            path_re = re.compile(r"^(.*?):(\d+):(.*)$")
            for _path, matches in grep_matches.items():
                for match in matches:
                    m = path_re.match(match)
                    if m:
                        file_part = m.group(1)
                        if file_part:
                            relevant_files.add(_to_rel(file_part))
            self.logger.debug(f"Relevant files from grep matches: {sorted(relevant_files)}")

        # Try LLM-based planning first if gateway is available
        if self.llm_gateway is not None and relevant_files:
            try:
                return self._plan_with_llm(
                    issue, relevant_files, source_files, grep_matches, repo_root
                )
            except Exception as e:
                self.logger.warning(
                    f"LLM planning failed: {e}. Falling back to deterministic planning."
                )

        # Deterministic fallback planning
        plan: List[PlanStep] = []
        step_id = 1

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

    def _plan_with_llm(
        self,
        issue: str,
        relevant_files: set,
        source_files: list,
        grep_matches: dict,
        repo_root: str,
    ) -> List[PlanStep]:
        """Use the LLM to generate specific plan steps based on issue and context."""
        # Build a concise summary of grep matches for the LLM
        match_summary = []
        for path, matches in grep_matches.items():
            rel_path = _to_rel(path) if path else path
            for match in matches[:5]:  # Limit to first 5 matches per file
                match_summary.append(f"  {rel_path}: {match[:200]}")

        matches_text = "\n".join(match_summary) if match_summary else "  (none)"

        files_text = "\n".join(f"  {f}" for f in sorted(relevant_files))

        prompt = f"""You are a software engineering planner. Analyze the GitHub issue and the code context below, then produce a resolution plan.

ISSUE: {issue}

RELEVANT SOURCE FILES (identified by grep matching issue keywords):
{files_text}

GREP MATCHES (code lines containing issue-related terms):
{matches_text}

TASK: For each relevant file, describe SPECIFIC code changes needed to resolve the issue. Be concrete — mention functions, line ranges, or logic to modify. Do NOT say "Apply issue-related changes" — describe what actually needs to change.

Respond with a JSON array of plan steps, each with:
- step_id (integer, starting at 1)
- action: "edit_file"
- target_file: relative path to the file (e.g., "url-api/src/service.ts")
- description: specific description of the code change needed
- estimated_tokens: integer (e.g., 1500)

Only include files that genuinely need changes. Output ONLY the JSON array, no markdown fences, no extra text."""

        self.logger.debug(f"LLM planning prompt length: {len(prompt)} chars")

        from pydantic import BaseModel as _BaseModel

        class _PlanStep(_BaseModel):
            step_id: int
            action: str
            target_file: str
            description: str
            estimated_tokens: int

        class _Plan(_BaseModel):
            steps: List[_PlanStep]

        response = self.llm_gateway.execute_structured(
            prompt=prompt,
            response_model=_Plan,
            temperature=0.1,
            max_tokens=4000,
        )

        plan: List[PlanStep] = []
        for s in response.steps:
            # Validate target_file exists and is not a URL/worktree path
            tf = s.target_file
            if tf.startswith(("http://", "https://")):
                self.logger.warning(f"Skipping URL target: {tf}")
                continue
            # Skip worktree-internal paths
            if "worktrees" in tf:
                self.logger.warning(f"Skipping worktree-internal path: {tf}")
                continue
            rel = _to_rel(tf)
            plan.append(PlanStep(
                step_id=s.step_id,
                action=s.action,
                target_file=rel,
                description=s.description,
                estimated_tokens=s.estimated_tokens,
            ))

        if not plan:
            self.logger.warning("LLM returned no valid plan steps; using deterministic fallback")
            # Fall through to deterministic below

        self.logger.info(f"LLM plan generated with {len(plan)} steps")
        for step in plan:
            self.logger.debug(f"  step {step.step_id}: {step.action} -> {step.target_file} ({step.description[:100]})")
        self.logger.success(f"LLM plan generated with {len(plan)} steps")
        return plan