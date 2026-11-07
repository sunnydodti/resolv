import os
import ast
from pathlib import Path
from agents.base import SubAgent
from core.logger import ResolvLogger
from typing import List, Union


class CodeGraphSubAgent(SubAgent):
    """
    Performs deterministic codebase exploration.
    Operations: GrepFiles, ParseAST, FindReferences, BuildDependencyGraph, ListDirectoryTree.
    """

    def __init__(self, logger: ResolvLogger, config):
        super().__init__(logger, config)

    def grep_files(self, paths: Union[List[str], str], patterns: Union[List[str], str]) -> list:
        """Search for pattern(s) in specified paths.

        Args:
            paths: A single path or list of file/directory paths to search.
            patterns: A single pattern string or list of pattern strings to search for.

        Returns:
            List of match strings in the format "path:line:content".
        """
        if isinstance(paths, str):
            paths = [paths]
        if isinstance(patterns, str):
            patterns = [patterns]

        results = []
        seen = set()
        self.logger.debug(f"GrepFiles: searching for {len(patterns)} pattern(s) in {len(paths)} path(s)")

        for p in paths:
            path = Path(p)
            if path.is_file():
                file_iter = [path]
            elif path.is_dir():
                file_iter = [f for f in path.rglob("*") if f.is_file()]
            else:
                self.logger.debug(f"Skipping non-existent path: {p}")
                continue

            for file_path in file_iter:
                # Skip binary-ish / large files
                try:
                    if file_path.stat().st_size > 2_000_000:
                        continue
                except OSError:
                    continue

                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        for i, line in enumerate(f, 1):
                            for pattern in patterns:
                                if pattern and pattern in line:
                                    match_key = f"{file_path}:{i}"
                                    if match_key in seen:
                                        continue
                                    seen.add(match_key)
                                    results.append(f"{file_path}:{i}:{line.strip()}")
                except Exception:
                    pass

        self.logger.success(f"Found {len(results)} matches for {len(patterns)} pattern(s)")
        for r in results[:10]:
            self.logger.debug(f"  match: {r}")
        if len(results) > 10:
            self.logger.debug(f"  ... and {len(results) - 10} more matches")
        return results

    def parse_ast(self, file_path: str) -> dict:
        """Parse Python file into AST structure. Skips directories and non-Python files."""
        self.logger.debug(f"ParseAST: analyzing {file_path}")
        path = Path(file_path)
        if path.is_dir():
            self.logger.debug(f"Skipping directory: {file_path}")
            return {"file": file_path, "functions": [], "classes": []}
        if path.suffix.lower() != ".py":
            self.logger.debug(f"Skipping non-Python file: {file_path}")
            return {"file": file_path, "functions": [], "classes": []}
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read())
        except SyntaxError as e:
            self.logger.warning(f"Syntax error parsing {file_path}: {e}")
            return {"file": file_path, "functions": [], "classes": [], "error": str(e)}
        except Exception as e:
            self.logger.warning(f"Failed to parse {file_path}: {e}")
            return {"file": file_path, "functions": [], "classes": [], "error": str(e)}
        return {
            "file": file_path,
            "functions": [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)],
            "classes": [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)],
        }