import logging
import sys
from typing import Optional

# ANSI Color Codes for TrueColor — Vibrant Material Design colors
COLORS = {
    "I": "\033[38;2;33;150;243m",  # Blue 500 — Info
    "S": "\033[38;2;76;175;80m",   # Green 500 — Success
    "W": "\033[38;2;255;152;0m",   # Orange 500 — Warning
    "E": "\033[38;2;244;67;54m",   # Red 500 — Error
    "D": "\033[38;2;156;39;176m",  # Purple 500 — Debug
    "H": "\033[38;2;3;169;244m",   # Light Blue 500 — Hint
    "?": "\033[1;38;2;255;255;255;48;2;33;150;243m",  # Bright White on Blue — Input Prompt
    "RESET": "\033[0m"
}

class ResolvLogger:
    def __init__(self, verbose: bool = False, log_file: Optional[str] = None):
        self.verbose = verbose
        self.log_file = log_file

    def _log(self, level: str, message: str):
        # ANSI-encoded for stdout
        color = COLORS.get(level, COLORS["RESET"])
        formatted_message = f"{color}[{level}]{COLORS['RESET']} {message}"
        print(formatted_message)

        # Plain text for file
        if self.log_file:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(f"[{level}] {message}\n")

    def info(self, msg): self._log("I", msg)
    def success(self, msg): self._log("S", msg)
    def warning(self, msg): self._log("W", msg)
    def error(self, msg): self._log("E", msg)
    def hint(self, msg): self._log("H", msg)
    def debug(self, msg):
        if self.verbose:
            self._log("D", msg)
    def prompt(self, msg: str):
        """Prompt user for input without trailing newline so input appears on same line."""
        color = COLORS.get("?", COLORS["RESET"])
        formatted_message = f"{color}[?]{COLORS['RESET']} {msg}"
        sys.stdout.write(formatted_message)
        sys.stdout.flush()
