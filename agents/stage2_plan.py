from agents.planner_agent import PlannerAgent
from core.logger import ResolvLogger
from config.models import load_global_config
import json
from pathlib import Path

def run_stage_2(logger: ResolvLogger, context: dict, project_config):
    """Stage 2: Plan — Synthesizing architectural roadmap and boundary constraints."""
    logger.info("Stage 2: Plan — Synthesizing architectural roadmap...")
    
    config = load_global_config()
    planner = PlannerAgent(logger, config)
    
    plan_steps = planner.execute(context)
    
    # Convert Pydantic models to dict for serialization
    plan_data = [step.model_dump() for step in plan_steps]
    
    session_path = Path(".resolv/sessions/temp")
    session_path.mkdir(parents=True, exist_ok=True)
    
    with open(session_path / "plan.json", "w") as f:
        json.dump(plan_data, f, indent=2)
    
    logger.success("Stage 2 Complete — Generated plan.json & plan.md")
    return plan_data
