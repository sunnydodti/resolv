import os
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
import yaml

class ProviderConfig(BaseModel):
    model: str
    api_key_env: str

class RepoConfig(BaseModel):
    source: str
    repopath: str
    credentialkey: str
    buildcmd: str
    testcmd: str
    lintcmd: str

class ProjectConfig(BaseModel):
    name: str
    description: str
    repos: Dict[str, RepoConfig]

class GlobalConfig(BaseModel):
    default_provider: str
    telemetry: Dict[str, str]
    providers: Dict[str, ProviderConfig]

def load_yaml(path: str) -> dict:
    with open(path, 'r') as f:
        return yaml.safe_load(f)

def load_global_config() -> GlobalConfig:
    conf = load_yaml('config/resolv.yaml')
    return GlobalConfig(**conf)
