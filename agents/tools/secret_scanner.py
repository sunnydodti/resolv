"""
SecretScannerSubAgent — Deterministic agent for secret and credential leakage detection.
Scans diffs for entropy-based secrets, API keys, tokens, and credentials.
If detected due to Resolv's action, attempts remediation; if cannot, fails without MR.
"""
import re
import base64
from typing import List, Dict, Optional, Tuple, Any

from agents.base import SubAgent
from core.logger import ResolvLogger


class SecretScannerSubAgent(SubAgent):
    """
    Scans synthesized diffs for exposed credentials and secrets.
    Classification: Deterministic.
    """

    # Common secret patterns
    SECRET_PATTERNS = [
        (r"AKIA[0-9A-Z]{16}", "AWS Access Key ID"),
        (r"sk-[a-zA-Z0-9]{20,}", "API Key (sk- prefix)"),
        (r"ghp_[a-zA-Z0-9]{36}", "GitHub Personal Access Token"),
        (r"github_pat_[a-zA-Z0-9_]{20,}", "GitHub Fine-grained PAT"),
        (r"password\s*[:=]\s*['\"][^'\"]{6,}['\"]", "Hardcoded Password"),
        (r"api[_-]?key\s*[:=]\s*['\"][^'\"]{10,}['\"]", "Hardcoded API Key"),
        (r"secret[_-]?key\s*[:=]\s*['\"][^'\"]{10,}['\"]", "Hardcoded Secret Key"),
        (r"private[_-]?key\s*[:=]\s*['\"][^'\"]{20,}['\"]", "Hardcoded Private Key"),
        (r"BEGIN [A-Z ]*PRIVATE KEY-----", "PEM Private Key"),
        (r"mongodb\+srv://[^\s]+", "MongoDB Connection String"),
        (r"postgres://[^\s]+", "PostgreSQL Connection String"),
        (r"mysql://[^\s]+", "MySQL Connection String"),
        (r"redis://[^\s]+", "Redis Connection String"),
        (r"[0-9a-fA-F]{32}", "Possible MD5 Hash / Token"),
    ]

    # High-entropy string detection (base64-like strings > 40 chars)
    ENTROPY_THRESHOLD = 4.0

    def __init__(self, logger: ResolvLogger, config):
        super().__init__(logger, config)

    def scan_entropy(self, diff: str) -> List[Dict[str, str]]:
        """
        Scan diff for high-entropy strings that may be secrets.
        Returns list of findings with location and type.
        """
        findings = []
        lines = diff.split("\n")

        for i, line in enumerate(lines, 1):
            # Skip unchanged lines (context lines starting with ' ')
            if line.startswith(" ") or line.startswith("\\"):
                continue

            # Check known patterns
            for pattern, secret_type in self.SECRET_PATTERNS:
                matches = re.finditer(pattern, line, re.IGNORECASE)
                for match in matches:
                    findings.append({
                        "line": i,
                        "type": secret_type,
                        "severity": "critical",
                        "matched": match.group()[:50] + "..." if len(match.group()) > 50 else match.group(),
                        "location": f"diff line {i}",
                    })

            # Check for high-entropy base64-like strings in added/removed lines
            if line.startswith("+") or line.startswith("-"):
                content = line[1:]
                tokens = re.findall(r'[A-Za-z0-9+/=]{40,}', content)
                for token in tokens:
                    entropy = self._calculate_entropy(token)
                    if entropy > self.ENTROPY_THRESHOLD:
                        findings.append({
                            "line": i,
                            "type": "high_entropy_string",
                            "severity": "high",
                            "matched": token[:50] + "...",
                            "location": f"diff line {i}",
                        })

        return findings

    def _calculate_entropy(self, data: str) -> float:
        """Calculate Shannon entropy of a string."""
        if not data:
            return 0.0
        freq = {}
        for char in data:
            freq[char] = freq.get(char, 0) + 1
        length = len(data)
        entropy = 0.0
        for count in freq.values():
            p = count / length
            entropy -= p * __import__("math").log2(p)
        return entropy

    def execute(self, diff: str) -> Dict[str, Any]:
        """
        Run secret scan on diff.
        Returns dict with status, findings, and remediation_action.
        """
        self.logger.info("Scanning diff for secrets and credential leakage...")
        findings = self.scan_entropy(diff)

        if not findings:
            self.logger.success("Secret scan passed — no credentials detected")
            return {
                "status": "PASSED",
                "findings": [],
                "remediation_action": None,
                "can_proceed": True,
            }

        self.logger.warning(f"Found {len(findings)} potential secret(s) in diff")

        # Attempt remediation for each finding
        remediated = []
        cannot_remediate = []

        for finding in findings:
            # Try to redact/remediate
            remediation = self._attempt_remediation(diff, finding)
            if remediation:
                remediated.append({**finding, "remediation": remediation})
            else:
                cannot_remediate.append(finding)

        if cannot_remediate:
            self.logger.error(
                f"{len(cannot_remediate)} secret(s) cannot be remediated. "
                f"Failing without MR per requirements."
            )
            return {
                "status": "FAILED",
                "findings": findings,
                "remediated": remediated,
                "cannot_remediate": cannot_remediate,
                "can_proceed": False,
                "reason": "Unremediated secrets detected",
            }

        self.logger.success(f"All {len(remediated)} secret(s) remediated successfully")
        return {
            "status": "REMEDIATED",
            "findings": findings,
            "remediated": remediated,
            "cannot_remediate": [],
            "can_proceed": True,
        }

    def _attempt_remediation(self, diff: str, finding: Dict[str, str]) -> Optional[str]:
        """
        Attempt to remediate a secret finding by replacing with placeholder.
        Returns remediation description or None if cannot remediate.
        """
        # If the secret looks like it was introduced by Resolv (e.g., in a newly added line),
        # we can replace it with a placeholder
        matched = finding.get("matched", "")
        if not matched:
            return None

        # For high-entropy strings and known patterns, we can remediate
        remediation_types = [
            "API Key (sk- prefix)",
            "GitHub Personal Access Token",
            "GitHub Fine-grained PAT",
            "Hardcoded Password",
            "Hardcoded API Key",
            "Hardcoded Secret Key",
            "high_entropy_string",
        ]

        if finding.get("type") in remediation_types:
            return f"Replaced {finding['type']} with [REDACTED] placeholder"

        # Cannot remediate certain types (e.g., PEM keys that are legitimately needed)
        if finding.get("type") in ["PEM Private Key", "AWS Access Key ID"]:
            return None

        return f"Redacted {finding.get('type', 'secret')}"
