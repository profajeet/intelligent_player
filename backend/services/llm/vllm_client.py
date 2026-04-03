from typing import AsyncGenerator
from .base import BaseLLMClient, LLMError


class VLLMClient(BaseLLMClient):
    """
    Adapter for vLLM's OpenAI-compatible server.
    vLLM exposes the same /v1/chat/completions endpoint as OpenAI,
    so we delegate to the OpenAI SDK pointed at the local server.

    Typical usage:
        vllm serve meta-llama/Meta-Llama-3-8B-Instruct --port 8001

    Config:
        base_url = "http://localhost:8001/v1"
        model    = "meta-llama/Meta-Llama-3-8B-Instruct"  (must match served model)
        api_key  = "EMPTY"  (vLLM accepts any non-empty string)
    """

    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:8001/v1",
        api_key: str = "EMPTY",
    ):
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise ImportError("openai package is required: pip install openai")

        self.model   = model
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)

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
            raise LLMError("vllm", str(e)) from e

    async def stream(
        self, system: str, user: str, max_tokens: int = 1024
    ) -> AsyncGenerator[str, None]:
        try:
            s = await self._client.chat.completions.create(
                model=self.model,
                max_tokens=max_tokens,
                stream=True,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": user},
                ],
            )
            async for chunk in s:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except Exception as e:
            raise LLMError("vllm", str(e)) from e
