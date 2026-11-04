"""
ResourceFetchSubAgent — Deterministic agent for fetching linked resources.
Operations: FetchLinkedResources, FetchLinkedIssues, DiscoverTestRunners.
"""
import subprocess
from typing import List, Optional, Dict

from agents.base import SubAgent
from core.logger import ResolvLogger


class ResourceFetchSubAgent(SubAgent):
    """Handles fetching linked resources and discovering test runners."""

    def __init__(self, logger: ResolvLogger, config):
        super().__init__(logger, config)

    def fetch_linked_resources(self, urls: List[str]) -> List[dict]:
        """Fetch content from linked resources (docs, specs, etc.)."""
        results = []
        for url in urls:
            self.logger.debug(f"Fetching resource: {url}")
            try:
                import urllib.request
                with urllib.request.urlopen(url, timeout=10) as resp:
                    content = resp.read().decode("utf-8", errors="ignore")[:5000]
                    results.append({"url": url, "content": content, "status": "success"})
            except Exception as e:
                self.logger.warning(f"Failed to fetch {url}: {e}")
                results.append({"url": url, "content": "", "status": "failed", "error": str(e)})
        return results

    def fetch_linked_issues(self, issue_id: str) -> List[dict]:
        """Fetch linked GitHub issues for context."""
        self.logger.debug(f"Fetching linked issues for: {issue_id}")
        # Placeholder — would use GitHub API
        return []

    def discover_test_runners(self, repo_path: str) -> List[str]:
        """Discover available test runners in the repository."""
        self.logger.debug(f"Discovering test runners in: {repo_path}")
        runners = []
        import os
        # Check for common test frameworks
        if os.path.exists(os.path.join(repo_path, "pytest.ini")) or os.path.exists(os.path.join(repo_path, "pyproject.toml")):
            runners.append("pytest")
        if os.path.exists(os.path.join(repo_path, "package.json")):
            runners.append("npm test / jest")
        if os.path.exists(os.path.join(repo_path, "go.mod")):
            runners.append("go test")
        return runners
