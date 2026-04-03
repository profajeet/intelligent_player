from typing import AsyncGenerator
from .base import BaseLLMClient, LLMError


class GeminiClient(BaseLLMClient):
    """
    Adapter for Google Gemini models via the google-generativeai SDK.
    (gemini-1.5-pro, gemini-1.5-flash, gemini-2.0-flash, etc.)
    """

    def __init__(self, api_key: str, model: str = "gemini-1.5-flash"):
        try:
            import google.generativeai as genai
        except ImportError:
            raise ImportError(
                "google-generativeai package is required: "
                "pip install google-generativeai"
            )

        self.model = model
        genai.configure(api_key=api_key)
        self._genai = genai

    def _build_model(self, system: str):
        return self._genai.GenerativeModel(
            model_name=self.model,
            system_instruction=system,
        )

    async def complete(self, system: str, user: str, max_tokens: int = 1024) -> str:
        import asyncio

        try:
            model = self._build_model(system)

            def _sync():
                resp = model.generate_content(
                    user,
                    generation_config={"max_output_tokens": max_tokens},
                )
                return resp.text

            return await asyncio.get_event_loop().run_in_executor(None, _sync)
        except Exception as e:
            raise LLMError("gemini", str(e)) from e

    async def stream(
        self, system: str, user: str, max_tokens: int = 1024
    ) -> AsyncGenerator[str, None]:
        import asyncio
        import queue
        import threading

        result_q: queue.Queue = queue.Queue()

        def _sync_stream():
            try:
                model = self._build_model(system)
                resp  = model.generate_content(
                    user,
                    stream=True,
                    generation_config={"max_output_tokens": max_tokens},
                )
                for chunk in resp:
                    if chunk.text:
                        result_q.put(chunk.text)
            except Exception as exc:
                result_q.put(exc)
            finally:
                result_q.put(None)  # sentinel

        thread = threading.Thread(target=_sync_stream, daemon=True)
        thread.start()

        loop = asyncio.get_event_loop()
        while True:
            item = await loop.run_in_executor(None, result_q.get)
            if item is None:
                break
            if isinstance(item, Exception):
                raise LLMError("gemini", str(item)) from item
            yield item
