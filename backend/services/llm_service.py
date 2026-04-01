import os
from typing import AsyncGenerator
from openai import AsyncOpenAI

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLM_MODEL      = os.getenv("LLM_MODEL", "gpt-4o-mini")

_client: AsyncOpenAI | None = None


def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    return _client


# ── Summary ──────────────────────────────────────────────────────────────────

SUMMARY_SYSTEM = (
    "You are an expert study assistant. "
    "Summarize the provided video transcript clearly and concisely, "
    "using bullet points for key ideas and a short paragraph as an overview. "
    "Respond in the same language as the transcript."
)


async def stream_summary(transcript: str) -> AsyncGenerator[str, None]:
    """Yields summary text chunks as they arrive from the LLM."""
    client = get_client()
    stream = await client.chat.completions.create(
        model=LLM_MODEL,
        stream=True,
        messages=[
            {"role": "system", "content": SUMMARY_SYSTEM},
            {"role": "user",   "content": f"Transcript:\n\n{transcript[:12000]}"},
        ],
        max_tokens=1024,
        temperature=0.3,
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


async def generate_summary(transcript: str) -> str:
    """Non-streaming version that returns the full summary string."""
    parts = []
    async for chunk in stream_summary(transcript):
        parts.append(chunk)
    return "".join(parts)


# ── Questions ─────────────────────────────────────────────────────────────────

QUESTIONS_SYSTEM = (
    "You are an expert study assistant. "
    "Generate 10 thoughtful comprehension and critical-thinking questions "
    "based on the provided transcript. "
    "For each question, provide a concise model answer. "
    "Return ONLY a valid JSON array with objects: "
    '[{"question": "...", "answer": "..."}, ...]. '
    "No markdown, no preamble."
)


async def generate_questions(transcript: str) -> list[dict]:
    """Returns a list of {question, answer} dicts."""
    import json

    client = get_client()
    response = await client.chat.completions.create(
        model=LLM_MODEL,
        stream=False,
        messages=[
            {"role": "system", "content": QUESTIONS_SYSTEM},
            {"role": "user",   "content": f"Transcript:\n\n{transcript[:12000]}"},
        ],
        max_tokens=2048,
        temperature=0.4,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content or "[]"

    # Model may wrap in {"questions": [...]}
    parsed = json.loads(raw)
    if isinstance(parsed, list):
        return parsed
    for key in ("questions", "data", "items"):
        if key in parsed and isinstance(parsed[key], list):
            return parsed[key]
    return []


# ── Streaming Questions (SSE) ─────────────────────────────────────────────────

QUESTIONS_STREAM_SYSTEM = (
    "You are an expert study assistant. "
    "Generate 10 thoughtful questions with answers based on the transcript. "
    "Format each as:\nQ: <question>\nA: <answer>\n\n"
    "Respond in the same language as the transcript."
)


async def stream_questions(transcript: str) -> AsyncGenerator[str, None]:
    """Yields question/answer text chunks for SSE streaming."""
    client = get_client()
    stream = await client.chat.completions.create(
        model=LLM_MODEL,
        stream=True,
        messages=[
            {"role": "system", "content": QUESTIONS_STREAM_SYSTEM},
            {"role": "user",   "content": f"Transcript:\n\n{transcript[:12000]}"},
        ],
        max_tokens=2048,
        temperature=0.4,
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta
