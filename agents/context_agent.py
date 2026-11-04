from agents.base import BaseAgent
from core.logger import ResolvLogger
from agents.tools.codegraph import CodeGraphSubAgent
from agents.tools.database_agent import DatabaseAgent
from typing import Any

class ContextAgent(BaseAgent):
    """
    Conducts multi-modal codebase comprehension and context gathering.
    Hybrid agent: delegates deterministic tasks to sub-agents.
    """
    def __init__(self, logger: ResolvLogger, config):
        super().__init__(logger, config)
        self.codegraph = CodeGraphSubAgent(logger, config)
        self.database = DatabaseAgent(logger, config)

    def execute(self, issue_reference: str, repo_paths: list) -> dict:
        """Ingest issue and gather code context."""
        self.logger.info(f"Analyzing issue: {issue_reference}")
        context = {
            "issue": issue_reference,
            "symbols": [],
            "schemas": {}
        }

        for path in repo_paths:
            # Grep for issue-related symbols
            self.codegraph.grep_files([path], issue_reference)
            # Parse AST for structure
            context["symbols"].append(self.codegraph.parse_ast(path))

        self.logger.success("Context gathering complete")
        return context
