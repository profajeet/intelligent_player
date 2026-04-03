from typing import AsyncGenerator
from .base import BaseLLMClient, LLMError

DEFAULT_OLLAMA_URL = "http://localhost:11434"


class OllamaClient(BaseLLMClient):
    """
    Adapter for Ollama (local models: llama3, mistral, phi3, gemma, etc.)
    Communicates with the Ollama REST API directly via httpx.
    No SDK dependency — works with any Ollama version.
    """

    def __init__(
        self,
        model: str = "llama3",
        base_url: str = DEFAULT_OLLAMA_URL,
        api_key: str | None = None,   # unused; accepted for interface uniformity
    ):
        try:
            import httpx  # noqa: F401
        except ImportError:
            raise ImportError("httpx package is required: pip install httpx")

        self.model    = model
        self.base_url = base_url.rstrip("/")

    def _messages(self, system: str, user: str) -> list[dict]:
        return [
            {"role": "system",  "content": system},
            {"role": "user",    "content": user},
        ]

    async def complete(self, system: str, user: str, max_tokens: int = 1024) -> str:
        import httpx

        payload = {
            "model":   self.model,
            "messages": self._messages(system, user),
            "stream":  False,
            "options": {"num_predict": max_tokens},
        }
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    f"{self.base_url}/api/chat", json=payload
                )
                resp.raise_for_status()
                data = resp.json()
                return data.get("message", {}).get("content", "")
        except httpx.HTTPStatusError as e:
            raise LLMError("ollama", f"HTTP {e.response.status_code}: {e.response.text}") from e
        except Exception as e:
            raise LLMError("ollama", str(e)) from e

    async def stream(
        self, system: str, user: str, max_tokens: int = 1024
    ) -> AsyncGenerator[str, None]:
        import httpx
        import json

        payload = {
            "model":    self.model,
            "messages": self._messages(system, user),
            "stream":   True,
            "options":  {"num_predict": max_tokens},
        }
        try:
            async with httpx.AsyncClient(timeout=180) as client:
                async with client.stream(
                    "POST", f"{self.base_url}/api/chat", json=payload
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        content = data.get("message", {}).get("content", "")
                        if content:
                            yield content
                        if data.get("done"):
                            break
        except httpx.HTTPStatusError as e:
            raise LLMError("ollama", f"HTTP {e.response.status_code}: {e.response.text}") from e
        except Exception as e:
            raise LLMError("ollama", str(e)) from e
