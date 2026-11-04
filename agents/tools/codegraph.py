import os
import ast
from pathlib import Path
from agents.base import SubAgent
from core.logger import ResolvLogger

class CodeGraphSubAgent(SubAgent):
    """
    Performs deterministic codebase exploration.
    Operations: GrepFiles, ParseAST, FindReferences, BuildDependencyGraph, ListDirectoryTree.
    """
    def __init__(self, logger: ResolvLogger, config):
        super().__init__(logger, config)

    def grep_files(self, paths: list, pattern: str) -> list:
        """Search for pattern in specified paths."""
        results = []
        self.logger.debug(f"GrepFiles: searching for '{pattern}' in {paths}")
        for p in paths:
            path = Path(p)
            if path.is_file():
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    for i, line in enumerate(f, 1):
                        if pattern in line:
                            results.append(f"{p}:{i}:{line.strip()}")
            elif path.is_dir():
                for file in path.rglob('*'):
                    if file.is_file():
                        try:
                            with open(file, 'r', encoding='utf-8', errors='ignore') as f:
                                for i, line in enumerate(f, 1):
                                    if pattern in line:
                                        results.append(f"{file}:{i}:{line.strip()}")
                        except Exception:
                            pass
        self.logger.success(f"Found {len(results)} matches for '{pattern}'")
        return results

    def parse_ast(self, file_path: str) -> dict:
        """Parse Python file into AST structure."""
        self.logger.debug(f"ParseAST: analyzing {file_path}")
        with open(file_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())
        return {
            "file": file_path,
            "functions": [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)],
            "classes": [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        }
