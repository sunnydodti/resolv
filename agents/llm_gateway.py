"""
LiteLLM Gateway with Instructor integration.
Provides schema-validated LLM calls with NO fallback (fail-fast per requirements).
Provider MUST be explicitly selected via CLI menu. No auto-selection, no defaults.
"""
import json
import os
import litellm
from datetime import datetime, timezone
from pathlib import Path
from typing import Type, TypeVar, Optional, List, Dict, Any
from pydantic import BaseModel

from agents.base import BaseAgent
from core.logger import ResolvLogger
from config.models import GlobalConfig, ProviderConfig, CredentialsStore, resolve_config_value

T = TypeVar("T", bound=BaseModel)


def _log_llm_call(logger: ResolvLogger, log_file: Optional[str], direction: str,
                  provider: str, model: str, data: dict):
    """Write LLM call input/output to the session log file for audit/review."""
    if not log_file:
        return
    try:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "direction": direction,  # "request" or "response"
            "provider": provider,
            "model": model,
            "data": data,
        }
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        # Logging must never break the LLM call
        pass


class LiteLLMGateway(BaseAgent):
    """
    Multi-provider LLM gateway using LiteLLM + Instructor.
    Every call returns a Pydantic model (structured output).
    NO automatic fallback — if the selected provider fails, the agent fails early.
    Provider must be explicitly selected before any LLM call.
    """

    def __init__(
        self, logger: ResolvLogger, config: GlobalConfig,
        credential_store: Optional[CredentialsStore] = None,
    ):
        super().__init__(logger, config)
        self.providers: Dict[str, ProviderConfig] = config.providers
        self.config_default_provider = config.default_provider
        self.selected_provider: Optional[str] = None
        self.selected_model: Optional[str] = None
        self.credential_store = credential_store

        # Validate that config has providers
        if not self.providers:
            self.logger.error("No LLM providers configured in ~/.resolv/config.yaml")
            raise ValueError("No LLM providers configured")

        # Validate that default provider exists in config (config validation only)
        if self.config_default_provider not in self.providers:
            self.logger.error(
                f"Default provider '{self.config_default_provider}' not found in config. "
                f"Available: {list(self.providers.keys())}"
            )
            raise ValueError(f"Missing default provider: {self.config_default_provider}")

        # Resolve API keys from config (env: or cred: prefixes) for all providers
        for name, provider in self.providers.items():
            try:
                api_key = resolve_config_value(provider.api_key, credential_store)
                if api_key:
                    litellm.api_key = api_key
                    self.logger.debug(f"API key loaded for provider: {name}")
            except ValueError as e:
                self.logger.warning(
                    f"API key not resolved for provider '{name}': {e}. "
                    f"Provider will fail at call time if selected."
                )

    def select_provider(self, provider_name: str, model: Optional[str] = None):
        """
        Manually select a provider (called from CLI menu).
        This is the ONLY way to select a provider — no auto-selection.
        """
        if provider_name not in self.providers:
            self.logger.error(f"Provider '{provider_name}' not configured. Available: {list(self.providers.keys())}")
            raise ValueError(f"Unknown provider: {provider_name}")

        self.selected_provider = provider_name
        provider = self.providers[provider_name]
        self.selected_model = model or provider.model

        # Ensure API key is resolved for this provider — FAIL EARLY if missing
        try:
            api_key = resolve_config_value(provider.api_key, self.credential_store)
            if not api_key:
                raise ValueError("empty resolved api key")
        except ValueError as e:
            self.logger.error(
                f"API key not resolved for provider '{provider_name}': {e}. "
                f"Cannot proceed without credentials."
            )
            raise ValueError(f"Missing API key for {provider_name}")

        self.logger.info(f"LLM provider selected: {provider_name} ({self.selected_model})")

    def require_provider(self) -> str:
        """
        Return the currently selected provider.
        FAIL EARLY if no provider has been selected.
        """
        if not self.selected_provider:
            self.logger.error(
                "No LLM provider selected. "
                "Provider must be selected via CLI menu before any LLM call."
            )
            raise ValueError("No LLM provider selected")
        return self.selected_provider

    def get_available_providers(self) -> List[str]:
        """Return list of configured provider names."""
        return list(self.providers.keys())

    def execute_structured(
        self,
        prompt: str,
        response_model: Type[T],
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
    ) -> T:
        """
        Make an LLM call with Instructor-structured output.
        Returns a validated Pydantic model instance.
        NO fallback — provider failure raises an exception.
        Provider must be explicitly provided or previously selected.
        """
        from instructor import from_litellm

        # Resolve provider: explicit param > previously selected > FAIL
        provider_name = provider or self.require_provider()

        if provider_name not in self.providers:
            self.logger.error(f"Provider '{provider_name}' not configured")
            raise ValueError(f"Unknown provider: {provider_name}")

        provider_cfg = self.providers[provider_name]
        model_name = model or provider_cfg.model

        # Resolve API key — FAIL EARLY if missing
        try:
            api_key = resolve_config_value(provider_cfg.api_key, self.credential_store)
            if not api_key:
                raise ValueError("empty resolved api key")
        except ValueError as e:
            self.logger.error(
                f"API key not resolved for provider {provider_name}: {e}. "
                f"Failing fast (no fallback)."
            )
            raise ValueError(f"Missing API key for {provider_name}")

        # Set API key for this call
        litellm.api_key = api_key
        if provider_cfg.api_base:
            litellm.api_base = provider_cfg.api_base

        self.logger.debug(
            f"LLM call: provider={provider_name}, model={model_name}, "
            f"prompt_len={len(prompt)}, response_model={response_model.__name__}"
        )

        # Log LLM request
        _log_llm_call(
            self.logger,
            getattr(self.logger, "log_file", None),
            "request",
            provider_name,
            model_name,
            {
                "prompt": prompt,
                "response_model": response_model.__name__,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        )

        try:
            client = from_litellm(litellm.completion)
            response: T = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                response_model=response_model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            self.logger.success(f"LLM call succeeded: {provider_name}/{model_name}")

            # Log LLM response
            _log_llm_call(
                self.logger,
                getattr(self.logger, "log_file", None),
                "response",
                provider_name,
                model_name,
                {
                    "response": response.model_dump() if hasattr(response, "model_dump") else str(response),
                    "response_model": response_model.__name__,
                },
            )
            return response

        except Exception as e:
            # Log LLM error
            _log_llm_call(
                self.logger,
                getattr(self.logger, "log_file", None),
                "error",
                provider_name,
                model_name,
                {"error": str(e), "error_type": type(e).__name__},
            )
            self.logger.error(f"LLM call failed: {provider_name}/{model_name} — {e}")
            # NO FALLBACK — fail early per requirements
            raise

    def execute_text(
        self,
        prompt: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Make an LLM call returning raw text.
        Used for non-structured tasks.
        NO fallback — provider failure raises an exception.
        """
        provider_name = provider or self.require_provider()

        if provider_name not in self.providers:
            self.logger.error(f"Provider '{provider_name}' not configured")
            raise ValueError(f"Unknown provider: {provider_name}")

        provider_cfg = self.providers[provider_name]
        model_name = model or provider_cfg.model

        # Resolve API key — FAIL EARLY if missing
        try:
            api_key = resolve_config_value(provider_cfg.api_key, self.credential_store)
            if not api_key:
                raise ValueError("empty resolved api key")
        except ValueError as e:
            self.logger.error(
                f"API key not resolved for provider {provider_name}: {e}. "
                f"Failing fast (no fallback)."
            )
            raise ValueError(f"Missing API key: {provider_name}")

        litellm.api_key = api_key
        if provider_cfg.api_base:
            litellm.api_base = provider_cfg.api_base

        self.logger.debug(f"LLM text call: provider={provider_name}, model={model_name}")

        # Log LLM text request
        _log_llm_call(
            self.logger,
            getattr(self.logger, "log_file", None),
            "request",
            provider_name,
            model_name,
            {
                "prompt": prompt,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "type": "text",
            },
        )

        try:
            response = litellm.completion(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            content = response.choices[0].message.content
            if not content:
                self.logger.error(f"LLM returned empty content for {provider_name}/{model_name}")
                raise ValueError("Empty LLM response")
            self.logger.success(f"LLM text call succeeded: {provider_name}/{model_name}")

            # Log LLM text response
            _log_llm_call(
                self.logger,
                getattr(self.logger, "log_file", None),
                "response",
                provider_name,
                model_name,
                {
                    "response": content,
                    "type": "text",
                },
            )
            return content

        except Exception as e:
            # Log LLM error
            _log_llm_call(
                self.logger,
                getattr(self.logger, "log_file", None),
                "error",
                provider_name,
                model_name,
                {"error": str(e), "error_type": type(e).__name__, "type": "text"},
            )
            self.logger.error(f"LLM text call failed: {provider_name}/{model_name} — {e}")
            raise
