from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from models.schemas import DownloadRequest, DownloadFormat
from services.yt_service import (
    download_video_stream, get_video_title, extract_video_id
)

router = APIRouter()

_MIME = {
    DownloadFormat.MP4_HIGH:  "video/mp4",
    DownloadFormat.MP4_LOW:   "video/mp4",
    DownloadFormat.AUDIO_MP3: "audio/mpeg",
}

_EXT = {
    DownloadFormat.MP4_HIGH:  "mp4",
    DownloadFormat.MP4_LOW:   "mp4",
    DownloadFormat.AUDIO_MP3: "mp3",
}


@router.post("/video")
async def download_video(req: DownloadRequest):
    video_id = extract_video_id(req.youtube_url)
    if not video_id:
        raise HTTPException(status_code=400, detail="Invalid YouTube URL")

    try:
        title = await get_video_title(req.youtube_url)
    except Exception:
        title = video_id

    safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in title)[:80]
    ext        = _EXT[req.format]
    filename   = f"{safe_title}.{ext}"
    mime       = _MIME[req.format]

    async def generate():
        async for chunk in download_video_stream(req.youtube_url, fmt=req.format):
            yield chunk

    return StreamingResponse(
        generate(),
        media_type=mime,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Video-Title": safe_title,
        },
    )
