from agents.base import BaseAgent
from core.logger import ResolvLogger
from agents.tools.codegraph import CodeGraphSubAgent
from agents.tools.database_agent import DatabaseAgent
from typing import Any, List, Dict
from pathlib import Path
import re
import requests


class ContextAgent(BaseAgent):
    """
    Conducts multi-modal codebase comprehension and context gathering.
    Hybrid agent: delegates deterministic tasks to sub-agents.
    Detects project language from file extensions found in the repo.
    Fetches issue body from GitHub API for context.
    """

    # Source file extensions grouped by language (for language detection)
    LANGUAGE_EXTENSIONS = {
        "python": {".py"},
        "typescript": {".ts", ".tsx"},
        "javascript": {".js", ".jsx"},
        "go": {".go"},
        "java": {".java"},
        "ruby": {".rb"},
        "csharp": {".cs"},
        "php": {".php"},
        "rust": {".rs"},
        "cpp": {".cpp", ".cc", ".cxx", ".hpp", ".h"},
        "c": {".c", ".h"},
        "swift": {".swift"},
        "kotlin": {".kt", ".kts"},
        "dart": {".dart"},
        "scala": {".scala"},
        "clojure": {".clj", ".cljs", ".cljc"},
        "elixir": {".ex", ".exs"},
        "erlang": {".erl", ".hrl"},
        "haskell": {".hs"},
        "ocaml": {".ml", ".mli"},
        "fsharp": {".fs", ".fsx"},
        "r": {".r"},
        "julia": {".jl"},
        "lua": {".lua"},
        "perl": {".pl", ".pm"},
    }

    # All source code extensions combined (used for code discovery and grep)
    SOURCE_EXTENSIONS = set()
    for _exts in LANGUAGE_EXTENSIONS.values():
        SOURCE_EXTENSIONS.update(_exts)

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

    def _detect_language(self, source_files: List[str]) -> str:
        """Detect the primary programming language from source file extensions."""
        ext_counts: Dict[str, int] = {}
        for f in source_files:
            ext = Path(f).suffix.lower()
            for lang, exts in self.LANGUAGE_EXTENSIONS.items():
                if ext in exts:
                    ext_counts[lang] = ext_counts.get(lang, 0) + 1
                    break

        if not ext_counts:
            return "unknown"

        # Return the language with the most files
        return max(ext_counts, key=ext_counts.get)

    def _fetch_issue_body(self, issue_reference: str) -> str:
        """Fetch the issue body from GitHub API if the reference is a GitHub URL."""
        if not (issue_reference.startswith("http://") or issue_reference.startswith("https://")):
            return ""
        if "/issues/" not in issue_reference:
            return ""

        try:
            # Parse: https://github.com/owner/repo/issues/123
            parts = issue_reference.rstrip("/").split("/")
            # Find "github.com" index
            github_idx = -1
            for i, p in enumerate(parts):
                if "github.com" in p:
                    github_idx = i
                    break
            if github_idx == -1 or github_idx + 3 >= len(parts):
                return ""

            owner = parts[github_idx + 1]
            repo = parts[github_idx + 2]
            # Find "issues" index
            issues_idx = -1
            for i, p in enumerate(parts):
                if p == "issues":
                    issues_idx = i
                    break
            if issues_idx == -1 or issues_idx + 1 >= len(parts):
                return ""

            issue_number = parts[issues_idx + 1]
            api_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}"

            self.logger.info(f"Fetching issue body from: {api_url}")
            resp = requests.get(api_url, timeout=15, headers={"Accept": "application/vnd.github.v3+json"})
            if resp.status_code == 200:
                data = resp.json()
                body = data.get("body", "") or ""
                self.logger.info(f"Fetched issue body ({len(body)} chars)")
                return body
            elif resp.status_code == 404:
                self.logger.warning(f"Issue not found on GitHub: {issue_reference}")
                return ""
            else:
                self.logger.warning(f"GitHub API returned {resp.status_code} for {api_url}")
                return ""
        except Exception as e:
            self.logger.warning(f"Failed to fetch issue body: {e}")
            return ""

    def _extract_issue_keywords(self, issue_reference: str, issue_body: str = "") -> List[str]:
        """Extract searchable keywords from an issue reference and body."""
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
        # Also extract keywords from issue body (first 500 chars)
        if issue_body:
            # Extract meaningful words from the body
            body_words = re.findall(r'\b[a-zA-Z]{4,}\b', issue_body[:500].lower())
            for w in body_words:
                if w not in keywords and w not in ("issue", "bug", "fix", "error", "feature", "add", "remove", "update", "change"):
                    keywords.append(w)
        self.logger.debug(f"Extracted issue keywords: {keywords}")
        return keywords

    def execute(self, issue_reference: str, repo_paths: list) -> dict:
        """Ingest issue and gather code context."""
        self.logger.info(f"Analyzing issue: {issue_reference}")

        # Fetch issue body from GitHub API
        issue_body = self._fetch_issue_body(issue_reference)

        context: Dict[str, Any] = {
            "issue": issue_reference,
            "issue_body": issue_body,
            "issue_summary": f"Auto-resolving issue: {issue_reference}",
            "affected_files": [],
            "required_changes": [],
            "extracted_symbols": [],
            "dependency_graph": {},
            "database_schema": {},
            "token_budget_used": 0,
            "token_budget_remaining": 0,
            "symbols": [],
            "schemas": {},
            "source_files": [],
            "grep_matches": {},
            "repo_root": str(Path(repo_paths[0]).resolve()) if repo_paths else "",
            "language": "unknown",
        }

        keywords = self._extract_issue_keywords(issue_reference, issue_body)

        for path in repo_paths:
            self.logger.info(f"Scanning repo path: {path}")

            # Discover actual source files (not just the directory)
            source_files = self._discover_source_files(path)
            context["source_files"].extend(source_files)

            # Detect language from file extensions
            if context["language"] == "unknown":
                context["language"] = self._detect_language(source_files)

            # Parse AST only for Python files (ast module only works for Python)
            for src_file in source_files:
                self.logger.debug(f"Parsing AST: {src_file}")
                if Path(src_file).suffix.lower() == ".py":
                    symbol_entry = self.codegraph.parse_ast(src_file)
                else:
                    symbol_entry = {
                        "file": src_file,
                        "functions": [],
                        "classes": [],
                        "skipped": f"not Python (suffix: {Path(src_file).suffix})",
                    }
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
            f"{total_symbols} symbols/functions/classes across {len(context['symbols'])} parsed files, "
            f"language: {context['language']}"
        )

        # Populate fields expected by analysis.md
        affected = context.get("affected_files", [])
        if not affected:
            # Use grep-matched files as affected files
            matched = set()
            for _path, matches in context.get("grep_matches", {}).items():
                for match in matches:
                    # match format: "absolute_path:line:content"
                    # Use rsplit from right because Windows paths contain colons (C:\...)
                    parts = match.rsplit(":", 2)
                    if len(parts) >= 2:
                        file_part = parts[0]
                        if file_part:
                            matched.add(file_part)
            affected = sorted(matched)
            context["affected_files"] = affected

        required = context.get("required_changes", [])
        if not required and affected:
            context["required_changes"] = [f"Apply issue-related changes to {f}" for f in affected]

        symbols_list = context.get("symbols", [])
        extracted = context.get("extracted_symbols", [])
        if not extracted and symbols_list:
            context["extracted_symbols"] = [
                {
                    "name": s.get("file", "").split("\\")[-1].split("/")[-1],
                    "type": "file",
                    "file": s.get("file", ""),
                    "line": 0,
                }
                for s in symbols_list
            ]

        self.logger.success("Context gathering complete")
        return context