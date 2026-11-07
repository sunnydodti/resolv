import os
from pathlib import Path

from config.models import get_resolv_dir

class WorkspaceManager:
    def __init__(self, project_name: str, issue_id: str):
        self.root = Path(get_resolv_dir() / "sessions" / project_name / issue_id)
        self.root.mkdir(parents=True, exist_ok=True)
    
    def get_path(self, filename: str) -> Path:
        return self.root / filename

    def initialize_metadata(self, issue_reference: str):
        import json
        import datetime
        metadata = {
            "session_id": os.urandom(8).hex(),
            "issue_reference": issue_reference,
            "current_stage": "STAGE_0_SETUP",
            "status": "IN_PROGRESS",
            "created_at": datetime.datetime.now().isoformat()
        }
        with open(self.get_path("metadata.json"), "w") as f:
            json.dump(metadata, f, indent=2)
        return self.get_path("metadata.json")
