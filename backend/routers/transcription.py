import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import io

from models.schemas import TranscriptionRequest, TranscriptionResponse, TranscriptSegment
from services.yt_service import get_video_info, get_captions, extract_video_id
from services.whisper_service import download_and_transcribe
from services.storage_service import get_transcript, save_transcript

router = APIRouter()


@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe(req: TranscriptionRequest):
    video_id = extract_video_id(req.youtube_url)
    if not video_id:
        raise HTTPException(status_code=400, detail="Invalid YouTube URL")

    # Return cached transcript if available
    cached = await get_transcript(video_id)
    if cached and not req.use_whisper:
        segments = json.loads(cached["segments"])
        return TranscriptionResponse(
            video_id=video_id,
            title=cached["title"],
            language=cached["language"],
            source=cached["source"],
            segments=[TranscriptSegment(**s) for s in segments],
            full_text=cached["full_text"],
        )

    # Get video metadata
    try:
        info = await get_video_info(req.youtube_url)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Could not fetch video info: {e}")

    title    = info.get("title", "Unknown")
    source   = "captions"
    segments = None

    if not req.use_whisper:
        try:
            segments = await get_captions(req.youtube_url, language=req.language)
        except Exception:
            segments = None

    if not segments:
        # Fall back to Whisper
        source = "whisper"
        try:
            segments = await download_and_transcribe(req.youtube_url, language=req.language)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Transcription failed: {e}")

    full_text = " ".join(s["text"] for s in segments)

    await save_transcript(
        video_id=video_id,
        title=title,
        language=req.language,
        source=source,
        full_text=full_text,
        segments_json=json.dumps(segments),
    )

    return TranscriptionResponse(
        video_id=video_id,
        title=title,
        language=req.language,
        source=source,
        segments=[TranscriptSegment(**s) for s in segments],
        full_text=full_text,
    )


@router.get("/transcript/{video_id}/download")
async def download_transcript(video_id: str, fmt: str = "txt"):
    """Download transcript as .txt or .srt"""
    cached = await get_transcript(video_id)
    if not cached:
        raise HTTPException(status_code=404, detail="Transcript not found for this video")

    segments = json.loads(cached["segments"])

    if fmt == "srt":
        content  = _to_srt(segments)
        filename = f"{video_id}_transcript.srt"
        media    = "text/srt"
    else:
        content  = cached["full_text"]
        filename = f"{video_id}_transcript.txt"
        media    = "text/plain"

    return StreamingResponse(
        io.BytesIO(content.encode("utf-8")),
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _to_srt(segments: list[dict]) -> str:
    lines = []
    for i, seg in enumerate(segments, 1):
        start = _srt_time(seg["start"])
        end   = _srt_time(seg["end"])
        lines.append(f"{i}\n{start} --> {end}\n{seg['text']}\n")
    return "\n".join(lines)


def _srt_time(seconds: float) -> str:
    ms = int((seconds % 1) * 1000)
    s  = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"
