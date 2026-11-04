"""
Credential Sub-Agent
Handles loading, resolving, and persisting credentials for a session.
Credentials can be raw values or env:<varname> references.
Stored in credentials.json within the session directory.
"""
import os
import re
from pathlib import Path
from typing import Dict, Optional

from agents.base import SubAgent
from core.logger import ResolvLogger
from config.models import CredentialsStore, CredentialEntry


class CredentialsSubAgent(SubAgent):
    """
    Deterministic sub-agent for credential management.
    Operations: LoadCredentials, ResolveCredential, SaveCredentials, PromptForMissing.
    """

    def __init__(self, logger: ResolvLogger, config):
        super().__init__(logger, config)

    def load_from_session(self, session_path: str) -> CredentialsStore:
        """Load existing credentials from session directory."""
        from config.models import load_credentials
        store = load_credentials(session_path)
        self.logger.debug(f"Loaded {len(store.credentials)} credentials from session")
        return store

    def save_to_session(self, session_path: str, store: CredentialsStore):
        """Persist credentials to session directory."""
        from config.models import save_credentials
        save_credentials(session_path, store)
        self.logger.success(f"Saved {len(store.credentials)} credentials to session")

    def add_credential(self, store: CredentialsStore, key: str, raw_value: Optional[str] = None,
                       env_ref: Optional[str] = None) -> CredentialsStore:
        """Add a credential to the store."""
        store.add(key=key, value=raw_value, env_ref=env_ref)
        self.logger.info(f"Added credential: {key}")
        return store

    def resolve(self, store: CredentialsStore, key: str) -> str:
        """Resolve a credential value at runtime."""
        try:
            value = store.get(key)
            self.logger.debug(f"Resolved credential: {key}")
            return value
        except (KeyError, ValueError) as e:
            self.logger.error(f"Failed to resolve credential {key}: {e}")
            raise

    def parse_env_ref(self, value_str: str) -> tuple[Optional[str], Optional[str]]:
        """
        Parse a credential string that may be raw or env:<varname>.
        Returns (raw_value, env_ref).
        """
        if value_str is None:
            return None, None
        if value_str.startswith("env:"):
            env_var = value_str[4:]
            return None, env_var
        return value_str, None

    def validate_all_resolved(self, store: CredentialsStore) -> bool:
        """Ensure all credentials can be resolved. Fail early if any cannot."""
        for key in store.credentials:
            try:
                store.get(key)
            except (KeyError, ValueError) as e:
                self.logger.error(f"Credential validation failed: {e}")
                return False
        self.logger.success("All credentials resolved successfully")
        return True
