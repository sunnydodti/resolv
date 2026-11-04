from typing import TypedDict, List, Optional
from pydantic import BaseModel, Field

class ContextState(TypedDict):
    """
    The core state object for the LangGraph workflow.
    """
    session_id: str
    issue_reference: str
    current_stage: str
    status: str
    
    # Analysis/Context
    code_context: Optional[str]
    db_schema: Optional[str]
    
    # Planning
    resolution_plan: Optional[str]
    
    # Execution
    modified_files: List[str]
    test_results: Optional[str]
    
    # Metadata
    error_trace: Optional[str]
    healing_turns: int
