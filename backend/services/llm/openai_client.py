from typing import AsyncGenerator
from .base import BaseLLMClient, LLMError


class OpenAIClient(BaseLLMClient):
    """
    Adapter for OpenAI chat models (gpt-4o, gpt-4o-mini, gpt-3.5-turbo, etc.)
    and any OpenAI-compatible endpoint (e.g. Azure OpenAI).
    """

    def __init__(self, api_key: str, model: str = "gpt-4o-mini", base_url: str | None = None):
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise ImportError("openai package is required: pip install openai")

        self.model  = model
        self._client = AsyncOpenAI(
            api_key=api_key,
            **({"base_url": base_url} if base_url else {}),
        )

    async def complete(self, system: str, user: str, max_tokens: int = 1024) -> str:
        try:
            resp = await self._client.chat.completions.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": user},
                ],
            )
            return resp.choices[0].message.content or ""
        except Exception as e:
            raise LLMError("openai", str(e)) from e

    async def stream(
        self, system: str, user: str, max_tokens: int = 1024
    ) -> AsyncGenerator[str, None]:
        try:
            stream = await self._client.chat.completions.create(
                model=self.model,
                max_tokens=max_tokens,
                stream=True,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": user},
                ],
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except Exception as e:
            raise LLMError("openai", str(e)) from e
