from typing import AsyncGenerator
from .base import BaseLLMClient, LLMError


class AnthropicClient(BaseLLMClient):
    """
    Adapter for Anthropic Claude models
    (claude-opus-4-5, claude-sonnet-4-5, claude-haiku-4-5, etc.)
    """

    def __init__(self, api_key: str, model: str = "claude-haiku-4-5-20251001"):
        try:
            import anthropic
        except ImportError:
            raise ImportError("anthropic package is required: pip install anthropic")

        self.model   = model
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def complete(self, system: str, user: str, max_tokens: int = 1024) -> str:
        try:
            msg = await self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return msg.content[0].text if msg.content else ""
        except Exception as e:
            raise LLMError("anthropic", str(e)) from e

    async def stream(
        self, system: str, user: str, max_tokens: int = 1024
    ) -> AsyncGenerator[str, None]:
        try:
            async with self._client.messages.stream(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            ) as s:
                async for text in s.text_stream:
                    yield text
        except Exception as e:
            raise LLMError("anthropic", str(e)) from e
