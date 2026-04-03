"""
Central factory.
Given a provider name + config dict, returns the correct BaseLLMClient subclass.
Nothing outside this package needs to import individual adapters.
"""

from .base import BaseLLMClient, LLMProvider, LLMError
from .openai_client    import OpenAIClient
from .anthropic_client import AnthropicClient
from .gemini_client    import GeminiClient
from .ollama_client    import OllamaClient
from .vllm_client      import VLLMClient


def build_client(provider: str, config: dict) -> BaseLLMClient:
    """
    Factory function.

    Args:
        provider: One of the LLMProvider enum values (case-insensitive string).
        config:   Dict with provider-specific keys (api_key, model, base_url, …).
                  Unknown keys are silently ignored so callers can pass the full
                  DB row without filtering.

    Returns:
        A concrete BaseLLMClient ready to call.

    Raises:
        LLMError: If the provider name is not recognised.
    """
    p = provider.lower()

    if p == LLMProvider.OPENAI:
        return OpenAIClient(
            api_key=config["api_key"],
            model=config.get("model", "gpt-4o-mini"),
            base_url=config.get("base_url"),
        )

    if p == LLMProvider.ANTHROPIC:
        return AnthropicClient(
            api_key=config["api_key"],
            model=config.get("model", "claude-haiku-4-5-20251001"),
        )

    if p == LLMProvider.GEMINI:
        return GeminiClient(
            api_key=config["api_key"],
            model=config.get("model", "gemini-1.5-flash"),
        )

    if p == LLMProvider.OLLAMA:
        return OllamaClient(
            model=config.get("model", "llama3"),
            base_url=config.get("base_url", "http://localhost:11434"),
        )

    if p == LLMProvider.VLLM:
        return VLLMClient(
            model=config["model"],
            base_url=config.get("base_url", "http://localhost:8001/v1"),
            api_key=config.get("api_key", "EMPTY"),
        )

    raise LLMError(provider, f"Unknown provider '{provider}'", status_code=400)


__all__ = [
    "build_client",
    "BaseLLMClient",
    "LLMProvider",
    "LLMError",
]
