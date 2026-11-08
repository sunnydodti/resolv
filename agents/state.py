"""
LangGraph State Definition for Resolv workflow.
Defines the state object passed between all 7 stages.
"""
from typing import TypedDict, List, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field

from config.models import CodeContext, ResolutionPlan, ReviewResult, CredentialsStore


class SessionMetadata(BaseModel):
    """metadata.json schema."""
    session_id: str
    issue_reference: str
    current_stage: str
    status: str  # IN_PROGRESS, COMPLETED, FAILED, PAUSED
    created_at: str
    updated_at: str
    max_healing_turns: int = 3
    healing_turns_used: int = 0
    dry_run: bool = False
    analysis_only: bool = False


    analysis_only: bool = False


class ResolvState(TypedDict):
    """
    Core LangGraph state object.
    Passed between all stage nodes.
    """
    # Session identity
    session_id: str
    issue_reference: str
    issue_id: str  # Parsed from state; strictly required for commit message footer
    project_name: str
    session_path: str  # ~/.resolv/sessions/<project>/<issue_id>

    # Lifecycle
    current_stage: str
    status: str
    created_at: str
    updated_at: str

    # Configuration
    global_config: Optional[dict]
    project_config: Optional[dict]
    credentials: Optional[dict]  # Serialized CredentialsStore

    # LLM routing
    selected_provider: Optional[str]
    selected_model: Optional[str]

    # Stage 1: Analyze outputs
    context_data: Optional[dict]  # Serialized CodeContext
    analysis_md_path: Optional[str]

    # Stage 2: Plan outputs
    plan_data: Optional[dict]  # Serialized ResolutionPlan
    plan_md_path: Optional[str]

    # Stage 3: Apply outputs
    worktree_path: Optional[str]
    modified_files: List[str]
    diff_output: Optional[str]

    # Stage 4: Build/Test outputs
    test_results: Optional[dict]
    error_trace: Optional[str]
    healing_turns: int
    max_healing_turns: int

    # Stage 5: Review outputs
    security_result: Optional[dict]
    review_result: Optional[dict]  # Serialized ReviewResult

    # Stage 6: Publish outputs
    pr_url: Optional[str]
    pr_draft: bool
    branch_name: Optional[str]

    # Stage 7: Record outputs
    audit_log_path: Optional[str]
    langfuse_trace_id: Optional[str]
    token_usage: Optional[dict]
    cost_estimate: Optional[float]

    # Control flags
    dry_run: bool
    analysis_only: bool
    verbose: bool

    # Resume support
    resume_from_stage: Optional[str]
