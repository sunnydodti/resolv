from agents.tools.sandbox_runner import SandboxRunnerSubAgent
from core.logger import ResolvLogger
from config.models import load_global_config

def run_stage_4(logger: ResolvLogger, project_config, max_healing_turns: int = 3):
    """Stage 4: Build/Test — Execute tests with self-healing loop."""
    logger.info("Stage 4: Build/Test — Running sandboxed test suite...")
    
    config = load_global_config()
    runner = SandboxRunnerSubAgent(logger, config)
    
    test_cmd = project_config.repos.primary.testcmd if hasattr(project_config, 'repos') else "echo 'no tests'"
    build_cmd = project_config.repos.primary.buildcmd if hasattr(project_config, 'repos') else "echo 'no build'"
    
    turn = 0
    while turn < max_healing_turns:
        turn += 1
        logger.info(f"Test turn {turn}/{max_healing_turns}")
        
        # Run build
        build_result = runner.run_command(build_cmd)
        if build_result["returncode"] != 0:
            logger.warning(f"Build failed at turn {turn}")
            continue
        
        # Run tests
        test_result = runner.run_command(test_cmd)
        if test_result["returncode"] == 0:
            logger.success("Stage 4 Complete — All tests passed")
            return True
        
        logger.warning(f"Test failure detected at turn {turn}")
        if turn >= max_healing_turns:
            logger.error("Max healing turns reached. Proceeding to fail-safe.")
            return False
    
    return False
