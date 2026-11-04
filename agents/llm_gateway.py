import litellm
from core.logger import ResolvLogger
from config.models import GlobalConfig
from agents.base import BaseAgent

class LiteLLMGateway(BaseAgent):
    def __init__(self, logger: ResolvLogger, config: GlobalConfig):
        super().__init__(logger, config)
        # Initialize providers from config
        self.providers = config.providers
        self.default_model = self.providers[config.default_provider].model
        
        # Set API keys from environment
        for name, provider in self.providers.items():
            os_key = provider.api_key_env
            litellm.api_key = os.getenv(os_key)

    def execute(self, prompt: str, model: str = None) -> str:
        model = model or self.default_model
        self.logger.debug(f"Calling LLM: {model} with prompt: {prompt[:50]}...")
        
        try:
            response = litellm.completion(
                model=model,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content
        except Exception as e:
            self.logger.error(f"LLM call failed: {e}")
            raise e
