"""
BoundaryAuditSubAgent — Deterministic agent for auditing diff paths against workspace boundaries.
Ensures no files outside allowed paths are modified.
"""
from typing import List, Dict, Any, Optional

from agents.base import SubAgent
from core.logger import ResolvLogger


class BoundaryAuditSubAgent(SubAgent):
    """
    Audits synthesized diffs against workspace boundary constraints.
    Classification: Deterministic.
    """

    def __init__(self, logger: ResolvLogger, config):
        super().__init__(logger, config)

    def execute(self, diff: str, allowed_paths: List[str], forbidden: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Audit diff paths against boundaries.
        Returns dict with status and violations.
        """
        self.logger.info("Auditing diff paths against workspace boundaries...")

        # Extract file paths from diff
        changed_files = self._extract_changed_files(diff)
        violations = []

        forbidden = forbidden or []

        for filepath in changed_files:
            # Check against allowed paths
            allowed = False
            for allowed_path in allowed_paths:
                if filepath.startswith(allowed_path):
                    allowed = True
                    break

            if not allowed:
                violations.append({
                    "file": filepath,
                    "reason": f"Not in allowed paths: {allowed_paths}",
                    "severity": "high",
                })

            # Check against forbidden paths
            for forbid_path in forbidden:
                if filepath.startswith(forbid_path):
                    violations.append({
                        "file": filepath,
                        "reason": f"In forbidden path: {forbid_path}",
                        "severity": "critical",
                    })

        if violations:
            self.logger.warning(f"Found {len(violations)} boundary violation(s)")
            return {
                "status": "FAILED",
                "violations": violations,
                "can_proceed": False,
            }

        self.logger.success("Boundary audit passed — all files within allowed paths")
        return {
            "status": "PASSED",
            "violations": [],
            "can_proceed": True,
        }

    def _extract_changed_files(self, diff: str) -> List[str]:
        """Extract file paths from a unified diff."""
        files = []
        for line in diff.split("\n"):
            if line.startswith("+++ ") or line.startswith("--- "):
                # Extract path after a/ or b/ prefix
                parts = line.split("\t")[0]
                if parts.startswith("+++ "):
                    path = parts[4:]
                elif parts.startswith("--- "):
                    path = parts[4:]
                else:
                    continue
                # Remove a/ or b/ prefix
                if path.startswith("a/") or path.startswith("b/"):
                    path = path[2:]
                if path != "/dev/null" and path not in files:
                    files.append(path)
        return files
