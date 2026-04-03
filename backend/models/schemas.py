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


# ── LLM Configuration ────────────────────────────────────────────────────────

class LLMProviderEnum(str, Enum):
    OPENAI    = "openai"
    ANTHROPIC = "anthropic"
    GEMINI    = "gemini"
    OLLAMA    = "ollama"
    VLLM      = "vllm"


class LLMConfigCreate(BaseModel):
    """Payload to register a new LLM provider configuration."""
    name:       str                        # Human label, e.g. "My local Llama"
    provider:   LLMProviderEnum
    model:      str                        # e.g. "gpt-4o-mini", "llama3", "gemini-1.5-flash"
    api_key:    Optional[str] = None       # Required for cloud providers
    base_url:   Optional[str] = None       # Custom endpoint (Ollama, vLLM, Azure, etc.)
    extra:      Optional[dict] = None      # Any provider-specific extras
    set_active: bool = True                # Make this the active config immediately

    model_config = {"json_schema_extra": {
        "examples": [
            {
                "name": "GPT-4o Mini",
                "provider": "openai",
                "model": "gpt-4o-mini",
                "api_key": "sk-...",
                "set_active": True,
            },
            {
                "name": "Claude Haiku",
                "provider": "anthropic",
                "model": "claude-haiku-4-5-20251001",
                "api_key": "sk-ant-...",
                "set_active": True,
            },
            {
                "name": "Gemini Flash",
                "provider": "gemini",
                "model": "gemini-1.5-flash",
                "api_key": "AIza...",
                "set_active": True,
            },
            {
                "name": "Local Llama3",
                "provider": "ollama",
                "model": "llama3",
                "base_url": "http://localhost:11434",
                "set_active": True,
            },
            {
                "name": "vLLM Mistral",
                "provider": "vllm",
                "model": "mistralai/Mistral-7B-Instruct-v0.3",
                "base_url": "http://localhost:8001/v1",
                "api_key": "EMPTY",
                "set_active": True,
            },
        ]
    }}


class LLMConfigUpdate(BaseModel):
    """Partial update for an existing config (all fields optional)."""
    name:     Optional[str]  = None
    model:    Optional[str]  = None
    api_key:  Optional[str]  = None
    base_url: Optional[str]  = None
    extra:    Optional[dict] = None


class LLMConfigResponse(BaseModel):
    """Safe public view — api_key is masked."""
    id:         int
    name:       str
    provider:   str
    model:      str
    api_key:    Optional[str] = None   # always masked
    base_url:   Optional[str] = None
    extra:      Optional[dict] = None
    is_active:  int
    created_at: str
    updated_at: str


class LLMTestRequest(BaseModel):
    """Ask the active (or a specific) config to answer a test prompt."""
    config_id: Optional[int] = None   # None = use active
    prompt:    str = "Say hello in one sentence."
