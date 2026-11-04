import sys
from core.logger import ResolvLogger

class ResolvErrorHandler:
    def __init__(self, logger: ResolvLogger):
        self.logger = logger

    def handle_exception(self, exc_type, exc_value, traceback):
        """Global catch-all for unhandled exceptions."""
        self.logger.error(f"Unhandled exception: {exc_value}")
        self.logger.info("Performing graceful cleanup...")
        # Cleanup worktrees, close sessions, etc.
        sys.exit(1)

    def graceful_exit(self, code: int = 0):
        """Clean exit with session finalization."""
        self.logger.info("Shutting down Resolv agent...")
        sys.exit(code)
