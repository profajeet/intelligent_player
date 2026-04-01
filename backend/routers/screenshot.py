import base64
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from models.schemas import ScreenshotRequest, ScreenshotResponse
from services.storage_service import save_screenshot_record

router = APIRouter()

SCREENSHOT_DIR = "storage/screenshots"
BASE_URL       = os.getenv("BASE_URL", "http://localhost:8000")


@router.post("/capture", response_model=ScreenshotResponse)
async def capture_screenshot(req: ScreenshotRequest):
    # Decode base64 PNG
    try:
        header, _, data = req.frame_data.partition(",")
        image_bytes = base64.b64decode(data if data else req.frame_data)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 image data")

    # Validate it starts with PNG magic bytes
    if not image_bytes.startswith(b"\x89PNG"):
        raise HTTPException(status_code=400, detail="Only PNG frames are supported")

    filename = f"{req.video_id}_{uuid.uuid4().hex[:8]}.png"
    filepath = os.path.join(SCREENSHOT_DIR, filename)

    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    with open(filepath, "wb") as f:
        f.write(image_bytes)

    await save_screenshot_record(req.video_id, filename, req.video_timestamp)

    screenshot_url = f"{BASE_URL}/screenshots/{filename}"

    return ScreenshotResponse(
        screenshot_url=screenshot_url,
        filename=filename,
        video_id=req.video_id,
        video_timestamp=req.video_timestamp,
    )


@router.get("/list/{video_id}")
async def list_screenshots(video_id: str):
    """List all screenshots taken for a given video."""
    import aiosqlite
    from services.storage_service import DB_PATH

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT filename, video_timestamp, created_at FROM screenshots "
            "WHERE video_id = ? ORDER BY video_timestamp ASC",
            (video_id,),
        ) as cursor:
            rows = await cursor.fetchall()

    return [
        {
            "url":             f"{BASE_URL}/screenshots/{row['filename']}",
            "filename":        row["filename"],
            "video_timestamp": row["video_timestamp"],
            "created_at":      row["created_at"],
        }
        for row in rows
    ]
