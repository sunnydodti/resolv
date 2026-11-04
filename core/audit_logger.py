import re
from core.logger import ResolvLogger

def sanitize_log(text: str) -> str:
    """Strip ANSI codes and mask sensitive data from audit logs."""
    # Remove ANSI escape sequences
    ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
    clean = ansi_escape.sub('', text)
    
    # Mask API keys / tokens
    clean = re.sub(r'(api_key|token|secret)[\s=:]+["\']?([^\s"\']+)', r'\1: ***REDACTED***', clean, flags=re.IGNORECASE)
    
    return clean

class AuditLogger:
    def __init__(self, logger: ResolvLogger, log_path: str):
        self.logger = logger
        self.log_path = log_path

    def write(self, message: str, level: str = "I"):
        """Write sanitized log entry to audit file."""
        clean_msg = sanitize_log(f"[{level}] {message}")
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(clean_msg + "\n")
