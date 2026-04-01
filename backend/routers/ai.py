import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from models.schemas import AIRequest, SummaryResponse, QuestionsResponse, Question
from services.llm_service import (
    generate_summary, stream_summary,
    generate_questions, stream_questions,
)
from services.storage_service import get_transcript

router = APIRouter()


async def _resolve_transcript(req: AIRequest) -> str:
    transcript = req.transcript
    if not transcript:
        cached = await get_transcript(req.video_id)
        if not cached:
            raise HTTPException(
                status_code=404,
                detail="No transcript found. Call /transcription/transcribe first.",
            )
        transcript = cached["full_text"]
    return transcript


# ── Summary ───────────────────────────────────────────────────────────────────

@router.post("/summary", response_model=SummaryResponse)
async def summary(req: AIRequest):
    transcript = await _resolve_transcript(req)
    text = await generate_summary(transcript)
    return SummaryResponse(video_id=req.video_id, summary=text)


@router.post("/summary/stream")
async def summary_stream(req: AIRequest):
    """Server-Sent Events endpoint — streams summary tokens as they arrive."""
    transcript = await _resolve_transcript(req)

    async def event_generator():
        async for chunk in stream_summary(transcript):
            yield {"data": chunk}
        yield {"data": "[DONE]"}

    return EventSourceResponse(event_generator())


# ── Questions ─────────────────────────────────────────────────────────────────

@router.post("/questions", response_model=QuestionsResponse)
async def questions(req: AIRequest):
    transcript = await _resolve_transcript(req)
    raw = await generate_questions(transcript)
    qs  = [Question(**q) for q in raw if "question" in q and "answer" in q]
    return QuestionsResponse(video_id=req.video_id, questions=qs)


@router.post("/questions/stream")
async def questions_stream(req: AIRequest):
    """SSE endpoint — streams Q&A text tokens as they arrive."""
    transcript = await _resolve_transcript(req)

    async def event_generator():
        async for chunk in stream_questions(transcript):
            yield {"data": chunk}
        yield {"data": "[DONE]"}

    return EventSourceResponse(event_generator())
