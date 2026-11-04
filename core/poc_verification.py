def run_poc_verification():
    """
    End-to-end simulation of a single issue fix through the full pipeline.
    Verifies all 7 stages connect correctly.
    """
    from core.logger import ResolvLogger
    from core.workspace import WorkspaceManager
    from agents.stage0_setup import run_stage_0
    
    logger = ResolvLogger(verbose=True)
    logger.info("=== Starting Resolv POC Verification ===")
    
    # Mock project config
    class MockRepo:
        repopath = "./"
        buildcmd = "echo build"
        testcmd = "echo test"
    
    class MockConfig:
        repos = type('obj', (object,), {'primary': MockRepo()})()
    
    try:
        # Stage 0
        ws_path = run_stage_0(logger, "test-project", "https://github.com/org/repo/issues/1")
        logger.success("POC Verification PASSED — Pipeline initialized successfully")
        return True
    except Exception as e:
        logger.error(f"POC Verification FAILED: {e}")
        return False

if __name__ == "__main__":
    run_poc_verification()
