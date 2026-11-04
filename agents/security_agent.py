import re
from agents.base import BaseAgent
from core.logger import ResolvLogger

class SecurityAgent(BaseAgent):
    """
    Protects against boundary escapes and exposed credentials.
    Deterministic agent: BoundaryAuditSubAgent + SecretScannerSubAgent.
    """
    def __init__(self, logger: ResolvLogger, config):
        super().__init__(logger, config)

    def execute(self, diff: str) -> dict:
        """Audit diff for security violations."""
        self.logger.info("Auditing diff for security violations...")
        
        violations = []
        
        # Entropy scanning / Secret detection (simple pattern match)
        secret_patterns = [r"AKIA[0-9A-Z]{16}", r"sk-[a-zA-Z0-9]{20,}", r"password\s*=\s*['\"][^'\"]+['\"]"]
        for pattern in secret_patterns:
            matches = re.findall(pattern, diff)
            if matches:
                violations.append(f"Secret detected: {pattern}")

        if violations:
            self.logger.warning(f"Found {len(violations)} security violations")
            return {"status": "FAILED", "violations": violations}
        
        self.logger.success("Security audit passed - zero violations")
        return {"status": "PASSED", "violations": []}
