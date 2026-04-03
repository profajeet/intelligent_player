"""
AI generation endpoints.
All LLM calls go through get_active_client() so the provider is
swappable at runtime via /llm-config.
"""

import json
from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from models.schemas import AIRequest, SummaryResponse, QuestionsResponse, Question
from services.llm_config_service import get_active_client
from services.llm.base import LLMError
from services.storage_service import get_transcript

router = APIRouter()


# ── Prompts ───────────────────────────────────────────────────────────────────

SUMMARY_SYSTEM = (
    "You are an expert study assistant. "
    "Summarize the provided video transcript clearly and concisely. "
    "Use bullet points for key ideas and a short overview paragraph. "
    "Respond in the same language as the transcript."
)

QUESTIONS_SYSTEM = (
    "You are an expert study assistant. "
    "Generate exactly 10 thoughtful comprehension and critical-thinking questions "
    "based on the provided transcript. "
    "For each question provide a concise model answer. "
    "Return ONLY a valid JSON array: "
    '[{"question": "...", "answer": "..."}, ...]. '
    "No markdown, no preamble, no trailing text."
)

QUESTIONS_STREAM_SYSTEM = (
    "You are an expert study assistant. "
    "Generate 10 thoughtful questions with answers based on the transcript. "
    "Format each as:\nQ: <question>\nA: <answer>\n\n"
    "Respond in the same language as the transcript."
)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _resolve_transcript(req: AIRequest) -> str:
    if req.transcript:
        return req.transcript
    cached = await get_transcript(req.video_id)
    if not cached:
        raise HTTPException(
            status_code=404,
            detail="No transcript found. Call /transcription/transcribe first.",
        )
    return cached["full_text"]


def _transcript_user_msg(transcript: str) -> str:
    return f"Transcript:\n\n{transcript[:12000]}"


# ── Summary ───────────────────────────────────────────────────────────────────

@router.post("/summary", response_model=SummaryResponse)
async def summary(req: AIRequest):
    """Generate a full summary (blocking — waits for the complete response)."""
    transcript = await _resolve_transcript(req)
    try:
        client = await get_active_client()
        text   = await client.complete(
            system=SUMMARY_SYSTEM,
            user=_transcript_user_msg(transcript),
            max_tokens=1024,
        )
    except LLMError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    return SummaryResponse(video_id=req.video_id, summary=text)


@router.post("/summary/stream")
async def summary_stream(req: AIRequest):
    """Stream summary tokens via Server-Sent Events."""
    transcript = await _resolve_transcript(req)

    async def generator():
        try:
            client = await get_active_client()
            async for chunk in client.stream(
                system=SUMMARY_SYSTEM,
                user=_transcript_user_msg(transcript),
                max_tokens=1024,
            ):
                yield {"data": chunk}
            yield {"data": "[DONE]"}
        except LLMError as e:
            yield {"data": json.dumps({"error": str(e)})}

    return EventSourceResponse(generator())


# ── Questions ─────────────────────────────────────────────────────────────────

@router.post("/questions", response_model=QuestionsResponse)
async def questions(req: AIRequest):
    """Generate Q&A pairs (blocking — waits for the complete response)."""
    transcript = await _resolve_transcript(req)
    try:
        client = await get_active_client()
        raw    = await client.complete(
            system=QUESTIONS_SYSTEM,
            user=_transcript_user_msg(transcript),
            max_tokens=2048,
        )
    except LLMError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))

    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            for key in ("questions", "data", "items"):
                if key in parsed and isinstance(parsed[key], list):
                    parsed = parsed[key]
                    break
        qs = [Question(**q) for q in parsed if "question" in q and "answer" in q]
    except (json.JSONDecodeError, TypeError):
        qs = [Question(question="Raw response", answer=raw)]

    return QuestionsResponse(video_id=req.video_id, questions=qs)


@router.post("/questions/stream")
async def questions_stream(req: AIRequest):
    """Stream Q&A text tokens via Server-Sent Events."""
    transcript = await _resolve_transcript(req)

    async def generator():
        try:
            client = await get_active_client()
            async for chunk in client.stream(
                system=QUESTIONS_STREAM_SYSTEM,
                user=_transcript_user_msg(transcript),
                max_tokens=2048,
            ):
                yield {"data": chunk}
            yield {"data": "[DONE]"}
        except LLMError as e:
            yield {"data": json.dumps({"error": str(e)})}

    return EventSourceResponse(generator())
