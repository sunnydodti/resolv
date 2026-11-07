import subprocess
from agents.base import SubAgent
from core.logger import ResolvLogger

class SandboxRunnerSubAgent(SubAgent):
    """
    Executes tests and builds in isolated runtime environments.
    Operations: RunSandboxCommand, CheckBudget.
    """
    def __init__(self, logger: ResolvLogger, config):
        super().__init__(logger, config)

    def run_command(self, cmd: str, cwd: str = ".", timeout: int = 60) -> dict:
        """Execute a shell command in sandboxed environment."""
        if not cmd:
            self.logger.warning("No command to run, skipping")
            return {"returncode": 0, "stdout": "", "stderr": "No command"}
        self.logger.info(f"Sandbox run: {cmd}")
        try:
            result = subprocess.run(
                cmd, shell=True, cwd=cwd,
                capture_output=True, text=True, timeout=timeout
            )
            output = {
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr
            }
            if result.returncode == 0:
                self.logger.success("Command executed successfully")
            else:
                self.logger.error(f"Command failed with code {result.returncode}")
            return output
        except subprocess.TimeoutExpired:
            self.logger.error(f"Command timed out after {timeout}s")
            return {"returncode": -1, "stdout": "", "stderr": "Timeout"}
