from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
import yaml
import os
from datetime import datetime
from pathlib import Path


def get_resolv_dir() -> Path:
    """Get the Resolv config directory per OS.
    Linux/macOS: ~/.resolv/
    Windows: %USERPROFILE%\\.resolv\\
    """
    home = Path.home()
    return home / ".resolv"


def get_global_config_path() -> Path:
    return get_resolv_dir() / "config.yaml"


def get_project_config_path(project_name: str) -> Path:
    return get_resolv_dir() / "projects" / f"{project_name}.yaml"


# =============================================================================
# Credential Model
# =============================================================================
class CredentialEntry(BaseModel):
    """A single credential entry, either raw value or env reference."""
    key: str
    value: Optional[str] = None  # Raw value if provided directly
    env_ref: Optional[str] = None  # e.g., "GITHUB_API_TOKEN" for env:<GITHUB_API_TOKEN>
    resolved_value: Optional[str] = None  # Resolved at runtime

    def resolve(self) -> str:
        """Resolve the credential value at runtime."""
        if self.resolved_value:
            return self.resolved_value
        if self.value is not None:
            return self.value
        if self.env_ref:
            env_val = os.getenv(self.env_ref)
            if env_val is None:
                raise ValueError(f"Environment variable {self.env_ref} not set for credential {self.key}")
            self.resolved_value = env_val
            return env_val
        raise ValueError(f"Credential {self.key} has no value or env reference")


class CredentialsStore(BaseModel):
    """Store of all credentials for a session."""
    credentials: Dict[str, CredentialEntry] = Field(default_factory=dict)

    def add(self, key: str, value: Optional[str] = None, env_ref: Optional[str] = None):
        self.credentials[key] = CredentialEntry(key=key, value=value, env_ref=env_ref)

    def get(self, key: str) -> str:
        if key not in self.credentials:
            raise KeyError(f"Credential {key} not found in store")
        return self.credentials[key].resolve()

    def save_to_file(self, path: str):
        """Persist credentials to disk (without resolved values for security)."""
        data = {
            "credentials": {
                k: {"key": v.key, "value": v.value, "env_ref": v.env_ref}
                for k, v in self.credentials.items()
            }
        }
        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False)


# =============================================================================
# Provider Model
# =============================================================================
class ProviderConfig(BaseModel):
    model: str
    api_key_env: str
    api_base: Optional[str] = None


# =============================================================================
# Repository Model
# =============================================================================
class RepoConfig(BaseModel):
    source: str
    repopath: str
    credentialkey: str
    buildcmd: Optional[str] = None
    testcmd: Optional[str] = None
    lintcmd: Optional[str] = None


# =============================================================================
# Data Source Model
# =============================================================================
class DatabaseConfig(BaseModel):
    schema_source: Optional[str] = None
    migrations_path: Optional[str] = None


class OtherDataSource(BaseModel):
    path: str
    type: str  # e.g., "read-only-docs"


# =============================================================================
# Project Configuration
# =============================================================================
class ProjectConfig(BaseModel):
    name: str
    description: str
    repos: Dict[str, RepoConfig]
    reference: List[RepoConfig] = Field(default_factory=list)
    data: Optional[Dict[str, Any]] = None
    tokens: Optional[Dict[str, Dict[str, str]]] = None  # e.g., {"GITHUB_TOKEN": {"env": "GITHUB_API_TOKEN"}}


# =============================================================================
# Telemetry Model
# =============================================================================
class TelemetryConfig(BaseModel):
    enabled: bool = True
    platform: str = "langfuse"
    host: Optional[str] = None
    public_key_env: Optional[str] = None
    secret_key_env: Optional[str] = None


# =============================================================================
# Global Configuration
# =============================================================================
class GlobalConfig(BaseModel):
    default_provider: str
    telemetry: TelemetryConfig
    providers: Dict[str, ProviderConfig]


# =============================================================================
# Context Schema (Stage 1 Output)
# =============================================================================
class ExtractedSymbol(BaseModel):
    name: str
    type: str  # function, class, variable
    file: str
    line: int


class CodeContext(BaseModel):
    issue_summary: str
    required_changes: List[str] = Field(default_factory=list)
    affected_files: List[str] = Field(default_factory=list)
    extracted_symbols: List[ExtractedSymbol] = Field(default_factory=list)
    dependency_graph: Dict[str, List[str]] = Field(default_factory=dict)
    database_schema: Optional[Dict[str, Any]] = None
    token_budget_used: int = 0
    token_budget_remaining: int = 0


# =============================================================================
# Plan Schema (Stage 2 Output)
# =============================================================================
class PlanStep(BaseModel):
    step_id: int
    action: str  # edit, create, delete, refactor
    target_file: str
    description: str
    code_snippet: Optional[str] = None
    estimated_tokens: int = 0
    depends_on: List[int] = Field(default_factory=list)


class ResolutionPlan(BaseModel):
    architectural_strategy: str
    steps: List[PlanStep] = Field(default_factory=list)
    total_estimated_tokens: int = 0
    workspace_boundaries: List[str] = Field(default_factory=list)
    risk_level: str = "low"  # low, medium, high


# =============================================================================
# Review Schema (Stage 5 Output)
# =============================================================================
class SecurityFinding(BaseModel):
    severity: str  # critical, high, medium, low
    type: str  # secret_leak, boundary_escape, credential_exposure
    location: str
    description: str


class ReviewResult(BaseModel):
    status: str  # approved, rejected, needs_changes
    security_findings: List[SecurityFinding] = Field(default_factory=list)
    compliance_score: float = 1.0  # 0.0 to 1.0
    feedback: str = ""
    route_back_to: Optional[str] = None  # stage_1 or stage_2


# =============================================================================
# Loader Functions
# =============================================================================
def load_yaml(path: str) -> dict:
    with open(path, 'r') as f:
        return yaml.safe_load(f)


def load_global_config() -> GlobalConfig:
    conf = load_yaml(str(get_global_config_path()))
    return GlobalConfig(**conf)


def load_project_config(project_name: str) -> ProjectConfig:
    path = str(get_project_config_path(project_name))
    conf = load_yaml(path)
    return ProjectConfig(**conf)


def load_credentials(session_path: str) -> CredentialsStore:
    """Load credentials from credentials.json if it exists."""
    import json
    cred_path = os.path.join(session_path, "credentials.json")
    if not os.path.exists(cred_path):
        return CredentialsStore()
    with open(cred_path, 'r') as f:
        data = json.load(f)
    store = CredentialsStore()
    for key, val in data.get("credentials", {}).items():
        store.add(
            key=val.get("key", key),
            value=val.get("value"),
            env_ref=val.get("env_ref")
        )
    return store


def save_credentials(session_path: str, store: CredentialsStore):
    """Persist credentials to credentials.json."""
    import json
    cred_path = os.path.join(session_path, "credentials.json")
    data = {
        "credentials": {
            k: {"key": v.key, "value": v.value, "env_ref": v.env_ref}
            for k, v in store.credentials.items()
        }
    }
    with open(cred_path, 'w') as f:
        json.dump(data, f, indent=2)
