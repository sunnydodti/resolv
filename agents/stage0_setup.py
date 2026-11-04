from core.workspace import WorkspaceManager
from core.logger import ResolvLogger

def run_stage_0(logger: ResolvLogger, project_name: str, issue_reference: str):
    """Stage 0: Initialization & Setup"""
    logger.info("Stage 0: Setup — Establishing isolated session workspace...")
    
    issue_id = issue_reference.split('/')[-1]
    ws = WorkspaceManager(project_name, issue_id)
    ws.initialize_metadata(issue_reference)
    
    logger.success(f"Stage 0 Complete — Workspace ready at {ws.root}")
    return ws.root
