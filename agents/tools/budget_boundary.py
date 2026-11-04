"""
BudgetAndBoundarySubAgent — Deterministic agent for token budget and workspace boundary validation.
Operations: CalculateTokenBudget, ValidateBoundaries.
"""
from typing import List, Dict, Any

from agents.base import SubAgent
from core.logger import ResolvLogger


class BudgetAndBoundarySubAgent(SubAgent):
    """Handles token budget calculation and workspace boundary validation."""

    def __init__(self, logger: ResolvLogger, config):
        super().__init__(logger, config)
        self.token_budget = 100000  # Default token budget per session
        self.used_tokens = 0

    def calculate_token_budget(self, payload_size: int) -> dict:
        """Calculate remaining token budget for a given payload size."""
        estimated_cost = payload_size // 4  # Rough estimate: 4 chars per token
        remaining = self.token_budget - self.used_tokens - estimated_cost
        self.used_tokens += estimated_cost
        return {
            "payload_size": payload_size,
            "estimated_tokens": estimated_cost,
            "remaining_budget": max(0, remaining),
            "budget_exceeded": remaining < 0,
        }

    def validate_boundaries(self, file_list: List[str], allowed_paths: List[str]) -> dict:
        """Validate that all files are within allowed workspace boundaries."""
        violations = []
        for filepath in file_list:
            allowed = any(filepath.startswith(path) for path in allowed_paths)
            if not allowed:
                violations.append(filepath)

        if violations:
            self.logger.warning(f"Boundary violations: {violations}")
            return {
                "valid": False,
                "violations": violations,
                "allowed_paths": allowed_paths,
            }

        self.logger.debug(f"All {len(file_list)} files within boundaries")
        return {
            "valid": True,
            "violations": [],
            "allowed_paths": allowed_paths,
        }
