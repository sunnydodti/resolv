"""
LangfuseExporterSubAgent — Deterministic agent for Langfuse telemetry export.
Flushes trace metrics (token usage, latency, cost) to Langfuse backend.
"""
import os
import json
from datetime import datetime, timezone
from typing import Dict, Optional

try:
    from langfuse import Langfuse
    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False

from agents.base import SubAgent
from core.logger import ResolvLogger


class LangfuseExporterSubAgent(SubAgent):
    """
    Exports telemetry and traces to Langfuse.
    Supports cloud Langfuse with API keys from environment variables.
    """

    def __init__(self, logger: ResolvLogger, config):
        super().__init__(logger, config)
        self.langfuse_client = None
        self._initialize_client()

    def _initialize_client(self):
        """Initialize Langfuse client from environment variables."""
        if not LANGFUSE_AVAILABLE:
            self.logger.warning("langfuse package not installed. Telemetry will be local only.")
            return

        public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
        secret_key = os.getenv("LANGFUSE_SECRET_KEY")
        base_url = os.getenv("LANGFUSE_BASE_URL")

        if not public_key or not secret_key:
            self.logger.warning(
                "Langfuse API keys not found in environment. "
                "Set LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY."
            )
            return

        try:
            self.langfuse_client = Langfuse(
                public_key=public_key,
                secret_key=secret_key,
                host=base_url,
            )
            self.logger.success("Langfuse client initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize Langfuse client: {e}")

    def flush_trace(
        self,
        session_id: str,
        stage: str,
        metrics: Optional[dict] = None,
        trace_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Flush a trace to Langfuse with session metadata and metrics.
        Returns the trace ID.
        """
        if not self.langfuse_client:
            self.logger.debug("Langfuse client not available. Skipping telemetry export.")
            return None

        try:
            trace = self.langfuse_client.trace(
                id=trace_id or session_id,
                name=f"resolv-session-{session_id[:8]}",
                session_id=session_id,
                metadata={
                    "stage": stage,
                    "metrics": metrics or {},
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
            self.logger.debug(f"Langfuse trace flushed: {trace.id}")
            return trace.id
        except Exception as e:
            self.logger.error(f"Failed to flush Langfuse trace: {e}")
            return None

    def log_event(
        self,
        trace_id: str,
        event_name: str,
        data: Optional[dict] = None,
    ):
        """Log a span/event within a Langfuse trace."""
        if not self.langfuse_client:
            return
        try:
            self.langfuse_client.span(
                trace_id=trace_id,
                name=event_name,
                metadata=data or {},
            )
        except Exception as e:
            self.logger.debug(f"Failed to log Langfuse event: {e}")
