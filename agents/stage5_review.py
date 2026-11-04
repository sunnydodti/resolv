from agents.security_agent import SecurityAgent
from agents.review_agent import ReviewAgent
from core.logger import ResolvLogger
from config.models import load_global_config

def run_stage_5(logger: ResolvLogger, diff: str, project_config):
    """Stage 5: Review — Audit diff for security and policy compliance."""
    logger.info("Stage 5: Review — Auditing diff for security and compliance...")
    
    config = load_global_config()
    security_agent = SecurityAgent(logger, config)
    review_agent = ReviewAgent(logger, config)
    
    # Security audit
    security_result = security_agent.execute(diff)
    if security_result["status"] == "FAILED":
        logger.error("Stage 5 Failed — Security violations detected")
        return False
    
    # Guideline compliance review
    guidelines = ["PEP8", "Type hinting", "Docstrings"]
    review_result = review_agent.execute(diff, guidelines)
    
    if review_result["status"] == "APPROVED":
        logger.success("Stage 5 Complete — Zero violations detected")
        return True
    
    logger.warning("Stage 5 Failed — Guideline compliance issues")
    return False
