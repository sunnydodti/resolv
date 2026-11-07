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
# Config value prefix resolution
# =============================================================================
# Supported prefixes, in resolution order. A config value may be:
#   - literal (no prefix): used as-is
#   - env:VARNAME: resolved from the environment at runtime
#   - cred:KEY: resolved from the credential store at runtime
#     (the stored value may itself be env:VARNAME, resolved recursively)
SUPPORTED_PREFIXES = ("env:", "cred:")

# Field-name keywords that indicate a value is a secret by intent.
# When Resolv collects a value for such a field, it is automatically
# stored in the credential store and written to config.yaml as cred:<key>.
SECRET_FIELD_KEYWORDS = (
    "api_key", "secret_key", "public_key",
    "token", "password", "secret", "credential",
)


def split_prefix(value: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """Return (prefix, ref) if value starts with a supported prefix,
    else (None, value). Only the first matching prefix is returned."""
    if not value:
        return None, value
    for prefix in SUPPORTED_PREFIXES:
        if value.startswith(prefix):
            return prefix, value[len(prefix):]
    return None, value


def resolve_config_value(
    value: Optional[str],
    credential_store: Optional["CredentialsStore"] = None,
) -> str:
    """Resolve a config value through the supported prefixes.

    Resolution order is the order of SUPPORTED_PREFIXES. The first prefix
    that the value starts with is used. If that prefix resolves to a
    non-empty value it is returned; otherwise a ValueError is raised.
    A value with no prefix is treated as a literal.

    cred:KEY values may themselves be env:VARNAME and are resolved
    recursively against the credential store.
    """
    if value is None:
        return ""

    prefix, ref = split_prefix(value)

    if prefix is None:
        return value  # literal

    if prefix == "env:":
        resolved = os.getenv(ref or "", "")
        if resolved:
            return resolved
    elif prefix == "cred:":
        if credential_store is not None:
            store_val = credential_store.get_raw(ref or "")
            if store_val:
                return resolve_config_value(store_val, credential_store)

    # Prefix matched but resolved to empty -> error per spec.
    raise ValueError(f"Could not resolve config value: {value}")


def is_secret_field(field_name: str) -> bool:
    """Detect secret intent by field name (not by value)."""
    name = (field_name or "").lower()
    return any(kw in name for kw in SECRET_FIELD_KEYWORDS)


# =============================================================================
# Credential Model
# =============================================================================
class CredentialEntry(BaseModel):
    """A single credential entry.

    The stored ``value`` may be a literal, an ``env:VARNAME`` reference, or
    (rarely) a ``cred:KEY`` reference. ``env_ref`` is kept for backward
    compatibility with older credential.json files.
    """
    key: str
    value: Optional[str] = None  # stored value: literal or env:VAR or cred:KEY
    env_ref: Optional[str] = None  # deprecated; kept for backward compat
    resolved_value: Optional[str] = None  # cached resolved value

    def get_raw_value(self) -> Optional[str]:
        """Return the raw stored value (may be env:VAR or literal)."""
        if self.value is not None:
            return self.value
        if self.env_ref is not None:
            return f"env:{self.env_ref}"
        return None

    def resolve(
        self, credential_store: Optional["CredentialsStore"] = None
    ) -> str:
        """Resolve the credential value at runtime."""
        if self.resolved_value:
            return self.resolved_value
        raw = self.get_raw_value()
        if raw is None:
            raise ValueError(f"Credential {self.key} has no value or env reference")
        resolved = resolve_config_value(raw, credential_store)
        self.resolved_value = resolved
        return resolved


class CredentialsStore(BaseModel):
    """Store of all credentials for a session."""
    credentials: Dict[str, CredentialEntry] = Field(default_factory=dict)

    def add(
        self, key: str, value: Optional[str] = None, env_ref: Optional[str] = None
    ):
        if value is None and env_ref is not None:
            value = f"env:{env_ref}"
        self.credentials[key] = CredentialEntry(key=key, value=value, env_ref=env_ref)

    def get_raw(self, key: str) -> Optional[str]:
        """Return the raw stored value for a key (may be env:VAR or literal)."""
        if key not in self.credentials:
            return None
        return self.credentials[key].get_raw_value()

    def get(
        self, key: str, credential_store: Optional["CredentialsStore"] = None
    ) -> str:
        """Resolve and return the credential value for a key."""
        if key not in self.credentials:
            raise KeyError(f"Credential {key} not found in store")
        return self.credentials[key].resolve(credential_store)

    def save_to_file(self, path: str):
        """Persist credentials to disk (without resolved values for security).

        Accepts either a directory (joins "credentials.json") or a full file path.
        """
        save_credentials(path, self)


# =============================================================================
# Provider Model
# =============================================================================
class ProviderConfig(BaseModel):
    model: str
    api_key: str  # e.g. "env:OPENROUTER_API_KEY" or "cred:openrouter_key"
    api_base: Optional[str] = None


# =============================================================================
# Repository Model
# =============================================================================
class RepoConfig(BaseModel):
    source: str  # platform: github, gitlab, bitbucket, custom, etc.
    repopath: str
    base: Optional[str] = None  # base host: github.com, gitlab.com, self-hosted domain, etc.
    path: Optional[str] = None  # path after base: /org/folder/etc
    credentialkey: Optional[str] = None  # key into the credential store (optional; credentials live in credentials.json)
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
    repos: Dict[str, RepoConfig]
    reference: List[RepoConfig] = Field(default_factory=list)
    data: Optional[Dict[str, Any]] = None


# =============================================================================
# Telemetry Model
# =============================================================================
class TelemetryConfig(BaseModel):
    enabled: bool = True
    platform: str = "langfuse"
    host: Optional[str] = None  # e.g. "env:LANGFUSE_BASE_URL"
    public_key: Optional[str] = None  # e.g. "env:LANGFUSE_PUBLIC_KEY"
    secret_key: Optional[str] = None  # e.g. "env:LANGFUSE_SECRET_KEY"


# =============================================================================
# Global Configuration
# =============================================================================
class GlobalConfig(BaseModel):
    default_provider: str
    telemetry: TelemetryConfig
    providers: Dict[str, ProviderConfig]
    clone_root: Optional[str] = None  # base directory for cloned repositories


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
    dependency_graph: Dict[str, List[str]] = Field(default_factory=list)
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
# Config dict migration (backward compatibility)
# =============================================================================
def _migrate_config_dict(conf: dict) -> dict:
    """Normalize older config dicts to the current field names.

    Older global configs used:
      providers.<name>.api_key_env   -> api_key  (value was the env var name)
      telemetry.public_key_env       -> public_key
      telemetry.secret_key_env       -> secret_key
    The stored value was just the env var name (e.g. "OPENROUTER_API_KEY").
    We convert it to the prefixed form (e.g. "env:OPENROUTER_API_KEY").
    """
    if not isinstance(conf, dict):
        return conf

    conf = dict(conf)

    # Migrate providers
    providers = conf.get("providers")
    if isinstance(providers, dict):
        new_providers = {}
        for prov_name, prov_cfg in providers.items():
            if isinstance(prov_cfg, dict):
                pc = dict(prov_cfg)
                if "api_key_env" in pc and "api_key" not in pc:
                    env_name = pc.pop("api_key_env")
                    # Value may already carry the env: prefix; avoid doubling.
                    if isinstance(env_name, str) and env_name.startswith("env:"):
                        pc["api_key"] = env_name
                    elif env_name:
                        pc["api_key"] = f"env:{env_name}"
                    else:
                        pc["api_key"] = ""
                new_providers[prov_name] = pc
            else:
                new_providers[prov_name] = prov_cfg
        conf["providers"] = new_providers

    # Migrate telemetry
    telemetry = conf.get("telemetry")
    if isinstance(telemetry, dict):
        tc = dict(telemetry)
        if "public_key_env" in tc and "public_key" not in tc:
            env_name = tc.pop("public_key_env")
            if isinstance(env_name, str) and env_name.startswith("env:"):
                tc["public_key"] = env_name
            elif env_name:
                tc["public_key"] = f"env:{env_name}"
            else:
                tc["public_key"] = None
        if "secret_key_env" in tc and "secret_key" not in tc:
            env_name = tc.pop("secret_key_env")
            if isinstance(env_name, str) and env_name.startswith("env:"):
                tc["secret_key"] = env_name
            elif env_name:
                tc["secret_key"] = f"env:{env_name}"
            else:
                tc["secret_key"] = None
        conf["telemetry"] = tc

    return conf


# =============================================================================
# Loader Functions
# =============================================================================
def load_yaml(path: str) -> dict:
    with open(path, 'r') as f:
        return yaml.safe_load(f)


def load_global_config() -> GlobalConfig:
    conf = load_yaml(str(get_global_config_path()))
    conf = _migrate_config_dict(conf)
    return GlobalConfig(**conf)


def load_project_config(project_name: str) -> ProjectConfig:
    path = str(get_project_config_path(project_name))
    conf = load_yaml(path)
    conf = _migrate_config_dict(conf)
    return ProjectConfig(**conf)


def load_credentials(session_path: str) -> CredentialsStore:
    """Load credentials from credentials.json if it exists.

    Accepts either a directory (joins "credentials.json") or a full file path.
    """
    import json
    cred_path = Path(session_path)
    if cred_path.suffix.lower() != ".json":
        cred_path = cred_path / "credentials.json"
    if not cred_path.exists():
        return CredentialsStore()
    with open(cred_path, 'r') as f:
        data = json.load(f)
    store = CredentialsStore()
    for key, val in data.get("credentials", {}).items():
        # Support both old dict format and new simple string format.
        if isinstance(val, str):
            store.add(key=key, value=val)
        elif isinstance(val, dict):
            store.add(
                key=val.get("key", key),
                value=val.get("value"),
                env_ref=val.get("env_ref")
            )
    return store


def save_credentials(session_path: str, store: CredentialsStore):
    """Persist credentials to credentials.json.

    Accepts either a directory (joins "credentials.json") or a full file path.
    Persists without resolved values for security.
    """
    import json
    cred_path = Path(session_path)
    if cred_path.suffix.lower() != ".json":
        cred_path = cred_path / "credentials.json"
    cred_path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "credentials": {
            k: {
                field: val
                for field, val in (
                    ("key", v.key),
                    ("value", v.value),
                    ("env_ref", v.env_ref),
                )
                if val is not None
            }
            for k, v in store.credentials.items()
        }
    }
    with open(cred_path, 'w') as f:
        json.dump(data, f, indent=2)
