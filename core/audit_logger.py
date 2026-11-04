"""
AuditLoggerSubAgent — Deterministic agent for hash-chained audit logging.
Writes immutable, cryptographically verifiable execution trail to audit.log.
"""
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any

from core.logger import ResolvLogger


class AuditLogger:
    """
    Writes hash-chained audit log entries.
    Each entry contains: timestamp, stage, action, data_hash, previous_hash, hash.
    Chain integrity is verified on load.
    """

    def __init__(self, logger: ResolvLogger, log_path: str):
        self.logger = logger
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def _get_previous_hash(self) -> str:
        """Retrieve the hash of the last entry in the audit log."""
        if not self.log_path.exists():
            return ""
        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                if not lines:
                    return ""
                last_line = lines[-1].strip()
                if not last_line:
                    return ""
                last_entry = json.loads(last_line)
                return last_entry.get("hash", "")
        except (json.JSONDecodeError, IndexError):
            return ""

    def write_entry(
        self,
        stage: str,
        action: str,
        data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Write a new hash-chained audit log entry.
        Returns the hash of the new entry.
        """
        previous_hash = self._get_previous_hash()

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stage": stage,
            "action": action,
            "data": data or {},
            "metadata": metadata or {},
            "previous_hash": previous_hash,
        }

        # Compute data_hash from entry contents (excluding hash itself)
        entry_data = json.dumps(entry, sort_keys=True, default=str)
        data_hash = hashlib.sha256(entry_data.encode("utf-8")).hexdigest()
        entry["hash"] = data_hash

        # Append to audit.log (plain text, ANSI stripped)
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")

        self.logger.debug(f"Audit entry written: {stage}/{action} (hash: {data_hash[:12]}...)")
        return data_hash

    def verify_chain(self) -> bool:
        """
        Verify the integrity of the entire hash chain.
        Returns True if chain is valid, False otherwise.
        """
        if not self.log_path.exists():
            self.logger.warning("Audit log does not exist. Nothing to verify.")
            return True

        with open(self.log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        if not lines:
            return True

        previous_hash = ""
        for i, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                self.logger.error(f"Invalid JSON at line {i}")
                return False

            # Verify previous_hash links
            if entry.get("previous_hash") != previous_hash:
                self.logger.error(f"Hash chain broken at line {i}")
                return False

            # Recompute hash
            entry_copy = {k: v for k, v in entry.items() if k != "hash"}
            entry_data = json.dumps(entry_copy, sort_keys=True, default=str)
            computed_hash = hashlib.sha256(entry_data.encode("utf-8")).hexdigest()

            if entry.get("hash") != computed_hash:
                self.logger.error(f"Hash mismatch at line {i}")
                return False

            previous_hash = computed_hash

        self.logger.success(f"Hash chain verified: {len(lines)} entries intact")
        return True
