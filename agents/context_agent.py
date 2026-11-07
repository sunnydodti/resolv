from agents.base import BaseAgent
from core.logger import ResolvLogger
from agents.tools.codegraph import CodeGraphSubAgent
from agents.tools.database_agent import DatabaseAgent
from typing import Any, List, Dict
from pathlib import Path


class ContextAgent(BaseAgent):
    """
    Conducts multi-modal codebase comprehension and context gathering.
    Hybrid agent: delegates deterministic tasks to sub-agents.
    """

    # Source file extensions worth parsing for symbols
    SOURCE_EXTENSIONS = {".py", ".ts", ".js", ".tsx", ".jsx", ".go", ".java", ".rb", ".cs", ".php"}

    def __init__(self, logger: ResolvLogger, config):
        super().__init__(logger, config)
        self.codegraph = CodeGraphSubAgent(logger, config)
        self.database = DatabaseAgent(logger, config)

    def _discover_source_files(self, repo_path: str) -> List[str]:
        """Recursively discover source files under a repo path."""
        root = Path(repo_path)
        files: List[str] = []
        if not root.exists():
            self.logger.warning(f"Repo path does not exist: {repo_path}")
            return files

        skip_dirs = {".git", ".resolv", "resolv", "worktrees", "node_modules", ".venv", "__pycache__", "build", "dist", ".next"}

        for file_path in root.rglob("*"):
            if not file_path.is_file():
                continue
            # Skip files under VCS/resolv/build directories relative to repo root
            try:
                rel = file_path.relative_to(root)
            except ValueError:
                continue
            if any(part in skip_dirs for part in rel.parts):
                continue
            if file_path.suffix.lower() in self.SOURCE_EXTENSIONS:
                files.append(str(file_path))

        self.logger.debug(f"Discovered {len(files)} source files under {repo_path}")
        for f in files[:20]:
            self.logger.debug(f"  source file: {f}")
        if len(files) > 20:
            self.logger.debug(f"  ... and {len(files) - 20} more")
        return files

    def _extract_issue_keywords(self, issue_reference: str) -> List[str]:
        """Extract searchable keywords from an issue reference (URL or text)."""
        keywords: List[str] = []
        # Take the last path segment (e.g. issues/3 -> '3', or a slug)
        stripped = issue_reference.strip().rstrip("/")
        segments = stripped.split("/")
        if segments:
            last = segments[-1]
            if last and last not in ("issues", "pull", "pulls"):
                keywords.append(last)
        # Also split on common separators for multi-word slugs
        for kw in list(keywords):
            for part in kw.replace("-", " ").replace("_", " ").split():
                if part and part not in keywords:
                    keywords.append(part)
        self.logger.debug(f"Extracted issue keywords: {keywords}")
        return keywords

    def execute(self, issue_reference: str, repo_paths: list) -> dict:
        """Ingest issue and gather code context."""
        self.logger.info(f"Analyzing issue: {issue_reference}")
        context: Dict[str, Any] = {
            "issue": issue_reference,
            "symbols": [],
            "schemas": {},
            "source_files": [],
            "grep_matches": {},
            "repo_root": str(Path(repo_paths[0]).resolve()) if repo_paths else "",
        }

        keywords = self._extract_issue_keywords(issue_reference)

        for path in repo_paths:
            self.logger.info(f"Scanning repo path: {path}")

            # Discover actual source files (not just the directory)
            source_files = self._discover_source_files(path)
            context["source_files"].extend(source_files)

            # Parse AST for each source file individually
            for src_file in source_files:
                self.logger.debug(f"Parsing AST: {src_file}")
                symbol_entry = self.codegraph.parse_ast(src_file)
                context["symbols"].append(symbol_entry)

            # Grep for issue-related keywords in source files
            if keywords:
                grep_results = self.codegraph.grep_files(source_files, keywords)
                context["grep_matches"][path] = grep_results
                self.logger.info(f"Found {len(grep_results)} grep matches for issue keywords in {path}")
            else:
                # Fallback: grep the raw issue reference (may still find nothing)
                grep_results = self.codegraph.grep_files(source_files, issue_reference)
                context["grep_matches"][path] = grep_results
                self.logger.warning(
                    f"No issue keywords extracted; grep for raw reference returned {len(grep_results)} matches"
                )

        total_symbols = sum(len(s.get("functions", [])) + len(s.get("classes", [])) for s in context["symbols"])
        self.logger.info(
            f"Context gathering complete — {len(context['source_files'])} source files, "
            f"{total_symbols} symbols/functions/classes across {len(context['symbols'])} parsed files"
        )
        self.logger.success("Context gathering complete")
        return context