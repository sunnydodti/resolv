from abc import ABC, abstractmethod
from typing import Any
from core.logger import ResolvLogger

class BaseAgent(ABC):
    """
    Abstract Base Class for all Resolv Agents (Orchestrators and Sub-Agents).
    Provides consistent logging and interface contract.
    """
    def __init__(self, logger: ResolvLogger, config: Any):
        self.logger = logger
        self.config = config

    @abstractmethod
    def execute(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the agent's primary task."""
        pass

class SubAgent(BaseAgent):
    """Marker for low-level execution units (Deterministic/AI)."""
    pass
