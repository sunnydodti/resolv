"""
LiteLLM Gateway with Instructor integration.
Provides schema-validated LLM calls with NO fallback (fail-fast per requirements).
Provider MUST be explicitly selected via CLI menu. No auto-selection, no defaults.
"""
import os
import litellm
from typing import Type, TypeVar, Optional, List, Dict, Any
from pydantic import BaseModel

from agents.base import BaseAgent
from core.logger import ResolvLogger
from config.models import GlobalConfig, ProviderConfig

T = TypeVar("T", bound=BaseModel)


class LiteLLMGateway(BaseAgent):
    """
    Multi-provider LLM gateway using LiteLLM + Instructor.
    Every call returns a Pydantic model (structured output).
    NO automatic fallback — if the selected provider fails, the agent fails early.
    Provider must be explicitly selected before any LLM call.
    """

    def __init__(self, logger: ResolvLogger, config: GlobalConfig):
        super().__init__(logger, config)
        self.providers: Dict[str, ProviderConfig] = config.providers
        self.config_default_provider = config.default_provider
        self.selected_provider: Optional[str] = None
        self.selected_model: Optional[str] = None

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

        # Set API keys from environment for all configured providers (validation only)
        for name, provider in self.providers.items():
            env_var = provider.api_key_env
            api_key = os.getenv(env_var)
            if api_key:
                litellm.api_key = api_key
                self.logger.debug(f"API key loaded for provider: {name} from {env_var}")
            else:
                self.logger.warning(
                    f"API key not found for provider '{name}' (env: {env_var}). "
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

        # Ensure API key is set for this provider — FAIL EARLY if missing
        env_var = provider.api_key_env
        if not os.getenv(env_var):
            self.logger.error(
                f"API key environment variable {env_var} not set for provider '{provider_name}'. "
                f"Cannot proceed without credentials."
            )
            raise ValueError(f"Missing API key for {provider_name} ({env_var})")

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

        # Validate API key — FAIL EARLY if missing
        env_var = provider_cfg.api_key_env
        if not os.getenv(env_var):
            self.logger.error(
                f"API key env var {env_var} not set for provider {provider_name}. "
                f"Failing fast (no fallback)."
            )
            raise ValueError(f"Missing API key: {env_var}")

        # Set API key for this call
        litellm.api_key = os.getenv(env_var)
        if provider_cfg.api_base:
            litellm.api_base = provider_cfg.api_base

        self.logger.debug(
            f"LLM call: provider={provider_name}, model={model_name}, "
            f"prompt_len={len(prompt)}, response_model={response_model.__name__}"
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
            return response

        except Exception as e:
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

        env_var = provider_cfg.api_key_env
        if not os.getenv(env_var):
            self.logger.error(
                f"API key env var {env_var} not set for provider {provider_name}. "
                f"Failing fast (no fallback)."
            )
            raise ValueError(f"Missing API key: {env_var}")

        litellm.api_key = os.getenv(env_var)
        if provider_cfg.api_base:
            litellm.api_base = provider_cfg.api_base

        self.logger.debug(f"LLM text call: provider={provider_name}, model={model_name}")

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
            return content

        except Exception as e:
            self.logger.error(f"LLM text call failed: {provider_name}/{model_name} — {e}")
            raise
