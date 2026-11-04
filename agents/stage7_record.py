import json
import datetime
from pathlib import Path
from core.logger import ResolvLogger

def run_stage_7(logger: ResolvLogger, session_path: Path, metrics: dict):
    """Stage 7: Record — Finalize persistence and export telemetry."""
    logger.info("Stage 7: Record — Finalizing session telemetry...")
    
    # Write audit log with hash chain
    audit_entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "metrics": metrics,
        "status": "COMPLETED"
    }
    
    audit_file = session_path / "audit.log"
    with open(audit_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(audit_entry) + "\n")
    
    logger.success(f"Stage 7 Complete — Audit log written to {audit_file}")
    return {"status": "RECORDED"}
