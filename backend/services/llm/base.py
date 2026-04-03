"""
Base interface that every LLM provider adapter must implement.
All providers return the same types so the rest of the app is provider-agnostic.
"""

from abc import ABC, abstractmethod
from typing import AsyncGenerator
from enum import Enum


class LLMProvider(str, Enum):
    OPENAI    = "openai"
    ANTHROPIC = "anthropic"
    GEMINI    = "gemini"
    OLLAMA    = "ollama"
    VLLM      = "vllm"


class BaseLLMClient(ABC):
    """
    Every provider adapter subclasses this.
    Callers only depend on this interface — never on a concrete adapter.
    """

    @abstractmethod
    async def complete(self, system: str, user: str, max_tokens: int = 1024) -> str:
        """Return the full completion as a single string (blocking style)."""

    @abstractmethod
    async def stream(
        self, system: str, user: str, max_tokens: int = 1024
    ) -> AsyncGenerator[str, None]:
        """Yield text chunks as they stream from the model."""
        # `yield` makes this a generator; subclasses must do the same.
        raise NotImplementedError
        yield  # pragma: no cover — makes Python treat this as an async generator


class LLMError(Exception):
    """Raised when a provider call fails in a known way."""

    def __init__(self, provider: str, message: str, status_code: int = 500):
        self.provider    = provider
        self.status_code = status_code
        super().__init__(f"[{provider}] {message}")
