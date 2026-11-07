from pydantic import BaseModel
from agents.base import BaseAgent
from core.logger import ResolvLogger
from agents.tools.local_git import LocalGitSubAgent
from typing import List, Tuple, Optional
from pathlib import Path
import re


class PatchResult(BaseModel):
    modified_files: List[str]
    diff: str
    status: str


class CodingAgent(BaseAgent):
    """
    Applies code changes and synthesizes self-healing patches.
    Uses the LLM gateway to generate targeted code changes based on plan steps.
    Operates on logical code blocks (functions/classes) rather than full files
    to minimize token usage and maximize edit accuracy.
    All LLM parameters (max_tokens, temperature, context_lines) are read from
    the global config — no hardcoded values.
    """

    # Patterns for function/class definitions across C-style and Python-like languages
    _BLOCK_START_PATTERNS = [
        r'^\s*(?:export\s+)?(?:async\s+)?function\s+(\w+)',       # JS/TS function
        r'^\s*(?:export\s+)?(?:async\s+)?def\s+(\w+)',            # Python def
        r'^\s*(?:export\s+)?class\s+(\w+)',                        # class
        r'^\s*(?:export\s+)?(?:public|private|protected)\s+(?:async\s+)?(?:function\s+)?(\w+)\s*\(',  # method-like
    ]

    def __init__(self, logger: ResolvLogger, config, llm_gateway=None, global_config=None):
        super().__init__(logger, config)
        self.git_tool = LocalGitSubAgent(logger, config)
        self.llm_gateway = llm_gateway
        # Read LLM settings from global config (written during setup, respected on reruns)
        self.llm_max_tokens = getattr(global_config, 'llm_max_tokens', None) if global_config else None
        self.llm_temperature = getattr(global_config, 'llm_temperature', None) if global_config else None
        self.context_lines = getattr(global_config, 'llm_context_lines', 3) if global_config else 3
        self.max_chars = getattr(global_config, 'llm_max_chars', 10000) if global_config else 10000

    # ------------------------------------------------------------------
    # Block parsing (language-agnostic)
    # ------------------------------------------------------------------
    def _parse_blocks(self, content: str) -> List[Tuple[int, int, str]]:
        """
        Parse file content into logical blocks (functions/classes).

        Returns a list of (start_line, end_line, block_text) tuples.
        Blocks are non-overlapping and cover the entire file.
        Lines before the first definition form block 0.
        """
        lines = content.split("\n")
        block_starts: List[int] = []

        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue
            for pattern in self._BLOCK_START_PATTERNS:
                if re.match(pattern, line):
                    block_starts.append(i)
                    break

        if not block_starts:
            # No definitions found — whole file is one block
            return [(0, len(lines), content)]

        blocks: List[Tuple[int, int, str]] = []
        # Block 0: everything before the first definition
        if block_starts[0] > 0:
            blocks.append((0, block_starts[0], "\n".join(lines[:block_starts[0]])))

        # Blocks for each definition
        for idx, start in enumerate(block_starts):
            end = block_starts[idx + 1] if idx + 1 < len(block_starts) else len(lines)
            block_text = "\n".join(lines[start:end])
            blocks.append((start, end, block_text))

        return blocks

    def _find_matching_block(
        self, blocks: List[Tuple[int, int, str]], description: str
    ) -> Optional[Tuple[int, int, str]]:
        """
        Find the block that best matches the plan step description.
        Matches keywords from the description against block content.
        """
        if not blocks:
            return None

        desc_words = set(
            w.lower()
            for w in re.split(r"[^a-zA-Z0-9_]+", description or "")
            if len(w) > 3
        )
        if not desc_words:
            return None

        best_block: Optional[Tuple[int, int, str]] = None
        best_score = 0

        for block in blocks:
            block_text_lower = block[2].lower()
            score = sum(1 for w in desc_words if w in block_text_lower)
            if score > best_score:
                best_score = score
                best_block = block

        return best_block if best_score > 0 else None

    # ------------------------------------------------------------------
    # LLM-based block editing (Option A — v1)
    # ------------------------------------------------------------------
    def _synthesize_with_llm(
        self, worktree: Path, target_file: str, description: str
    ) -> bool:
        """
        Use the LLM gateway to generate targeted code changes for a logical block.

        Reads the file, parses it into blocks, finds the block matching the
        plan description, sends that block (with context) to the LLM, and
        applies the LLM's modified block back to the file.
        """
        file_path = worktree / target_file
        if not file_path.exists():
            self.logger.warning(f"Target file does not exist: {target_file}")
            return False

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                original = f.read()
        except Exception as e:
            self.logger.warning(f"Could not read {target_file}: {e}")
            return False

        if not original.strip():
            self.logger.warning(f"Target file is empty: {target_file}")
            return False

        blocks = self._parse_blocks(original)
        self.logger.debug(f"Parsed {len(blocks)} blocks from {target_file}")

        # Find the block that matches the plan description
        target_block = self._find_matching_block(blocks, description)

        if target_block is None:
            # No specific block matched — fall back to whole file (one LLM call)
            self.logger.debug(
                f"No block matched description for {target_file}; using whole file"
            )
            block_text = original
            block_start = 0
            block_end = len(original.split("\n"))
        else:
            block_start, block_end, block_text = target_block
            self.logger.debug(
                f"Using block lines {block_start + 1}-{block_end} for {target_file}"
            )

        # Build context: the block plus surrounding lines (configurable)
        lines = original.split("\n")
        context_lines = self.context_lines
        context_start = max(0, block_start - context_lines)
        context_end = min(len(lines), block_end + context_lines)
        context_lines_text = lines[context_start:context_end]
        context_text = "\n".join(context_lines_text)

        # Truncate if too large (configurable)
        if len(context_text) > self.max_chars:
            context_text = context_text[:self.max_chars] + "\n... (truncated)"

        prompt = f"""You are a software engineer fixing a GitHub issue. Below is a code block from a source file and a description of the change needed.

FILE: {target_file}
BLOCK LINES: {block_start + 1}-{block_end}
CHANGE NEEDED: {description}

CURRENT BLOCK CONTENTS (lines {context_start + 1}-{context_end} of the file):
```
{context_text}
```

TASK: Produce the COMPLETE modified block content that implements the requested change.
- Output ONLY the modified block content — no markdown fences, no explanations.
- Preserve the exact indentation and style of the original block.
- The output must be valid source code that can replace the original block directly.
- If no change is needed, output the original block content unchanged."""

        self.logger.debug(f"LLM coding prompt length: {len(prompt)} chars for {target_file}")

        from pydantic import BaseModel as _BaseModel

        class _BlockEdit(_BaseModel):
            file_path: str
            new_block_content: str

        try:
            response = self.llm_gateway.execute_structured(
                prompt=prompt,
                response_model=_BlockEdit,
                temperature=self.llm_temperature,
                max_tokens=self.llm_max_tokens,
            )

            new_block = response.new_block_content
            if not new_block or new_block.strip() == block_text.strip():
                self.logger.debug(f"LLM produced no meaningful change for {target_file} block")
                return False

            # Replace the block in the original content
            new_lines = (
                lines[:block_start]
                + [new_block]
                + lines[block_end:]
            )
            new_content = "\n".join(new_lines)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            self.logger.info(f"Applied LLM-generated edit to {target_file}")
            return True

        except Exception as e:
            self.logger.error(
                f"LLM code synthesis failed for {target_file}: {e}"
            )
            # NO FALLBACK — fail early per requirements
            raise

    def execute(self, plan_steps: list, worktree_path: str) -> PatchResult:
        """Apply structured edits based on plan steps."""
        self.logger.info("Applying code changes to worktree...")
        modified_files = []
        worktree = Path(worktree_path)

        # LLM-based code synthesis is required — no fallback
        if self.llm_gateway is None:
            self.logger.error("No LLM gateway available for coding")
            raise ValueError("CodingAgent requires an LLM gateway — no fallback allowed")

        for step in plan_steps:
            if isinstance(step, dict):
                action = step.get("action", "unknown")
                target_file = step.get("target_file", "")
                description = step.get("description", "")
            else:
                action = step.action
                target_file = step.target_file
                description = getattr(step, "description", "")
            self.logger.debug(f"Executing step: {action} -> {target_file}")
            # Skip non-file targets (e.g. issue URLs) and files that don't exist
            if not target_file or target_file.startswith(("http://", "https://")):
                self.logger.warning(f"Skipping non-file target: {target_file}")
                continue
            target_path = worktree / target_file
            if not target_path.exists():
                self.logger.warning(f"Target file does not exist in worktree: {target_file}")
                continue

            if action == "edit_file":
                applied = self._synthesize_with_llm(worktree, target_file, description)
                if not applied:
                    self.logger.warning(
                        f"LLM did not produce a change for {target_file} — skipping"
                    )
                    continue
                modified_files.append(target_file)
            else:
                self.logger.warning(f"Unknown action '{action}' for {target_file}, skipping")

        diff = self.git_tool.compute_diff(worktree_path)

        if not modified_files:
            self.logger.error("No target files were applied — no code changes were synthesized")
            raise RuntimeError(
                "Stage 3 failed: no source files were modified. "
                "The coding agent could not synthesize any code changes from the plan steps."
            )
        if not diff or not diff.strip():
            self.logger.error("Diff is empty — no actual code changes were written to disk")
            raise RuntimeError(
                "Stage 3 failed: git diff is empty after applying plan steps. "
                "No code changes were synthesized for the modified files."
            )

        self.logger.success(f"Applied changes to {len(modified_files)} files")
        return PatchResult(
            modified_files=modified_files,
            diff=diff,
            status="APPLIED"
        )