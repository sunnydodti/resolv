import json
from pathlib import Path
from agents.state import ContextState

class CheckpointManager:
    def __init__(self, session_path: Path):
        self.checkpoint_file = session_path / "metadata.json"

    def save(self, state: ContextState):
        with open(self.checkpoint_file, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, default=str)

    def load(self) -> ContextState:
        if not self.checkpoint_file.exists():
            return {}
        with open(self.checkpoint_file, "r", encoding="utf-8") as f:
            return json.load(f)
