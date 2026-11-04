import logging
import sys
from typing import Optional

# ANSI Color Codes for TrueColor
COLORS = {
    "I": "\033[38;2;138;155;184m", # Soft Slate Blue
    "S": "\033[38;2;143;188;143m", # Soft Sage Green
    "W": "\033[38;2;222;198;134m", # Muted Pastel Yellow
    "E": "\033[38;2;212;142;142m", # Muted Terracotta
    "D": "\033[38;2;164;152;192m", # Dusty Lavender
    "H": "\033[38;2;135;184;212m", # Pale Sky Blue
    "P": "\033[30;48;2;210;215;220m", # Input Prompt
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
    def prompt(self, msg): self._log("P", msg)
