"""
Credential Sub-Agent
Handles loading, resolving, and persisting credentials for a session.
Credentials can be literal values, env:<varname> references, or
cred:<key> references into the credential store.
Stored in credentials.json within the session directory.
"""
import os
from pathlib import Path
from typing import Dict, Optional, Tuple

from agents.base import SubAgent
from core.logger import ResolvLogger
from config.models import (
    CredentialsStore,
    CredentialEntry,
    split_prefix,
    resolve_config_value,
)


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

    def add_credential(
        self, store: CredentialsStore, key: str, raw_value: Optional[str] = None,
        env_ref: Optional[str] = None,
    ) -> CredentialsStore:
        """Add a credential to the store. The stored value may be a literal
        or an env:VARNAME reference."""
        store.add(key=key, value=raw_value, env_ref=env_ref)
        self.logger.info(f"Added credential: {key}")
        return store

    def resolve(
        self, store: CredentialsStore, key: str
    ) -> str:
        """Resolve a credential value at runtime using the unified prefix resolver."""
        try:
            value = store.get(key, store)
            self.logger.debug(f"Resolved credential: {key}")
            return value
        except (KeyError, ValueError) as e:
            self.logger.error(f"Failed to resolve credential {key}: {e}")
            raise

    def get_raw(self, store: CredentialsStore, key: str) -> Optional[str]:
        """Return the raw stored value for a key (may be env:VAR or literal)."""
        return store.get_raw(key)

    def parse_prefix(self, value_str: str) -> Tuple[Optional[str], Optional[str]]:
        """Parse a value string into (prefix, ref).

        Supported prefixes: env:, cred:. Returns (None, value) for literals.
        """
        return split_prefix(value_str)

    def validate_all_resolved(
        self, store: CredentialsStore
    ) -> bool:
        """Ensure all credentials can be resolved. Fail early if any cannot."""
        for key in store.credentials:
            try:
                store.get(key, store)
            except (KeyError, ValueError) as e:
                self.logger.error(f"Credential validation failed: {e}")
                return False
        self.logger.success("All credentials resolved successfully")
        return True
