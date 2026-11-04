from core.logger import ResolvLogger

def run_dry_run(logger: ResolvLogger, pipeline_stages: list):
    """Execute pipeline through Stage 5, bypassing Stage 6 (Publish)."""
    logger.info("Dry-run mode: Executing through Stage 5 (Review)...")
    
    for stage in pipeline_stages:
        if stage == 6:  # Skip Publish
            logger.info(f"Skipping Stage {stage} (Publish) due to dry-run mode")
            continue
        logger.info(f"Executing Stage {stage}...")
    
    logger.success("Dry-run complete — No remote changes made")
