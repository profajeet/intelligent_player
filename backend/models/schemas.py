from pydantic import BaseModel, HttpUrl
from typing import Optional, List
from datetime import datetime
from enum import Enum


# ── Notes ──────────────────────────────────────────────────────────────────

class NoteOperation(str, Enum):
    INSERT = "insert"
    DELETE = "delete"
    UPDATE = "update"
    FULL   = "full"
    APPEND_SCREENSHOT = "append_screenshot"


class NoteDelta(BaseModel):
    op:           NoteOperation
    video_id:     str
    content:      Optional[str] = None
    position:     Optional[int] = None
    length:       Optional[int] = None
    screenshot_url: Optional[str] = None
    timestamp:    Optional[float] = None  # video timestamp in seconds


class NoteResponse(BaseModel):
    op:           NoteOperation
    video_id:     str
    content:      Optional[str] = None
    screenshot_url: Optional[str] = None
    saved_at:     datetime


# ── Transcription ───────────────────────────────────────────────────────────

class TranscriptionRequest(BaseModel):
    youtube_url: str
    language:    Optional[str] = "en"
    use_whisper: Optional[bool] = False   # force Whisper even if captions exist


class TranscriptSegment(BaseModel):
    start: float
    end:   float
    text:  str


class TranscriptionResponse(BaseModel):
    video_id:    str
    title:       str
    language:    str
    source:      str   # "captions" | "whisper"
    segments:    List[TranscriptSegment]
    full_text:   str


# ── AI ──────────────────────────────────────────────────────────────────────

class AIRequest(BaseModel):
    video_id:   str
    transcript: Optional[str] = None   # if None, fetched from DB
    language:   Optional[str] = "en"


class SummaryResponse(BaseModel):
    video_id: str
    summary:  str


class Question(BaseModel):
    question: str
    answer:   str


class QuestionsResponse(BaseModel):
    video_id:  str
    questions: List[Question]


# ── Download ────────────────────────────────────────────────────────────────

class DownloadFormat(str, Enum):
    MP4_HIGH  = "mp4_high"
    MP4_LOW   = "mp4_low"
    AUDIO_MP3 = "audio_mp3"


class DownloadRequest(BaseModel):
    youtube_url: str
    format:      DownloadFormat = DownloadFormat.MP4_HIGH


# ── Screenshot ──────────────────────────────────────────────────────────────

class ScreenshotRequest(BaseModel):
    video_id:          str
    frame_data:        str    # base64-encoded PNG
    video_timestamp:   float  # seconds into the video


class ScreenshotResponse(BaseModel):
    screenshot_url: str
    filename:       str
    video_id:       str
    video_timestamp: float
