# YouTube Study Tool

A full-stack application that transforms any YouTube video into an interactive study session. Watch videos, take real-time notes, capture screenshots directly into your notes, generate AI summaries and questions, download videos, and get full transcriptions — all in one place.

The AI backend is **provider-agnostic**: switch between OpenAI, Anthropic Claude, Google Gemini, Ollama (local), or vLLM at runtime without restarting the server.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
  - [Repository Structure](#repository-structure)
  - [System Architecture Diagram](#system-architecture-diagram)
  - [Backend Architecture](#backend-architecture)
  - [LLM Module Architecture](#llm-module-architecture)
  - [Frontend Architecture](#frontend-architecture)
  - [Data Flow](#data-flow)
  - [Database Schema](#database-schema)
  - [API Reference](#api-reference)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Installation Guide](#installation-guide)
  - [1. Clone the Repository](#1-clone-the-repository)
  - [2. Backend Setup](#2-backend-setup)
  - [3. Frontend Setup](#3-frontend-setup)
  - [4. Environment Variables](#4-environment-variables)
  - [5. Running the App](#5-running-the-app)
  - [Docker Setup](#docker-setup)
- [LLM Provider Setup](#llm-provider-setup)
  - [OpenAI](#openai)
  - [Anthropic Claude](#anthropic-claude)
  - [Google Gemini](#google-gemini)
  - [Ollama (Local)](#ollama-local)
  - [vLLM (Self-hosted)](#vllm-self-hosted)
  - [Switching Providers at Runtime](#switching-providers-at-runtime)
- [Configuration](#configuration)
- [Usage Guide](#usage-guide)
- [Development Guide](#development-guide)
  - [Adding a New LLM Provider](#adding-a-new-llm-provider)
- [Troubleshooting](#troubleshooting)

---

## Features

| Feature | Description |
|---|---|
| **Video Player** | Embedded YouTube player with full playback controls |
| **Real-time Notes** | Rich-text notes panel synced via WebSocket — edits persist instantly |
| **Screenshot Capture** | Capture the current video frame and embed it inline into your notes |
| **AI Summary** | Generate a structured summary of the video using the transcript |
| **AI Questions** | Auto-generate 10 comprehension & critical-thinking Q&A pairs |
| **Transcription** | Fetch YouTube captions or transcribe audio with OpenAI Whisper |
| **Download Transcript** | Export transcript as `.txt` or `.srt` subtitle file |
| **Download Video** | Download the video in high/low MP4 quality or audio-only MP3 |
| **Multi-provider LLM** | Plug in OpenAI, Anthropic, Gemini, Ollama, or vLLM via a single API call |
| **Runtime Provider Switching** | Swap the active AI provider without restarting the server |

---

## Architecture

### Repository Structure

```
youtube-study-tool/
│
├── frontend/                          # SvelteKit application
│   ├── src/
│   │   ├── routes/
│   │   │   ├── +page.svelte           # Landing page — YouTube URL input
│   │   │   └── watch/
│   │   │       └── +page.svelte       # Main study view (player + panels)
│   │   └── lib/
│   │       ├── components/
│   │       │   ├── VideoPlayer.svelte
│   │       │   ├── NotesPanel.svelte
│   │       │   ├── TranscriptPanel.svelte
│   │       │   ├── ScreenshotCapture.svelte
│   │       │   ├── SummaryView.svelte
│   │       │   └── QuestionsView.svelte
│   │       └── ws.ts                  # WebSocket client singleton
│   ├── package.json
│   └── svelte.config.js
│
├── backend/                           # FastAPI application
│   ├── main.py                        # App entry — CORS, routers, lifespan
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── requirements.txt
│   ├── .env.example
│   │
│   ├── models/
│   │   └── schemas.py                 # All Pydantic request/response models
│   │
│   ├── routers/
│   │   ├── notes.py                   # WS /ws/notes/{video_id}
│   │   ├── transcription.py           # POST /transcription/transcribe
│   │   ├── ai.py                      # POST /ai/summary, /ai/questions (SSE)
│   │   ├── download.py                # POST /download/video
│   │   ├── screenshot.py              # POST /screenshot/capture
│   │   └── llm_config.py              # CRUD /llm-config + /llm-config/test
│   │
│   ├── services/
│   │   ├── storage_service.py         # SQLite: notes, transcripts, screenshots
│   │   ├── yt_service.py              # yt-dlp: metadata, captions, streaming
│   │   ├── whisper_service.py         # Local speech-to-text transcription
│   │   ├── llm_config_service.py      # LLM config persistence + active client
│   │   └── llm/                       # Generic multi-provider LLM package
│   │       ├── __init__.py
│   │       ├── base.py                # BaseLLMClient ABC + LLMError
│   │       ├── registry.py            # build_client() factory
│   │       ├── openai_client.py       # OpenAI / Azure-compatible
│   │       ├── anthropic_client.py    # Anthropic Claude
│   │       ├── gemini_client.py       # Google Gemini
│   │       ├── ollama_client.py       # Ollama (local, no extra SDK)
│   │       └── vllm_client.py         # vLLM (self-hosted OpenAI-compatible)
│   │
│   └── storage/
│       ├── study_tool.db              # SQLite database (auto-created)
│       └── screenshots/               # Screenshot PNGs (auto-created)
│
├── docker-compose.yml                 # Root-level compose for full-stack dev
└── README.md
```

---

### System Architecture Diagram

```
┌───────────────────────────────────────────────────────────────────────────┐
│                            Browser (User)                                  │
│                                                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                        SvelteKit Frontend                            │  │
│  │                                                                      │  │
│  │  ┌──────────────┐  ┌─────────────┐  ┌──────────────┐  ┌──────────┐ │  │
│  │  │ Video Player │  │ Notes Panel │  │  Transcript  │  │ Summary/ │ │  │
│  │  │ (YT iframe + │  │ (WebSocket) │  │    Panel     │  │Questions │ │  │
│  │  │  canvas)     │  │             │  │              │  │  (SSE)   │ │  │
│  │  └──────┬───────┘  └──────┬──────┘  └──────┬───────┘  └────┬─────┘ │  │
│  └─────────┼─────────────────┼────────────────┼───────────────┼────────┘  │
│            │        REST / WebSocket / SSE     │               │           │
└────────────┼─────────────────┼────────────────┼───────────────┼───────────┘
             │                 │                │               │
             ▼                 ▼                ▼               ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                            FastAPI Backend                                 │
│                                                                            │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │
│  │/ws/notes     │ │/transcription│ │/ai/      │ │/download │ │/llm-   │ │
│  │(WebSocket)   │ │/screenshot   │ │summary   │ │/video    │ │config  │ │
│  │              │ │              │ │/questions│ │          │ │        │ │
│  └──────┬───────┘ └──────┬───────┘ └────┬─────┘ └────┬─────┘ └───┬────┘ │
│         │                │              │             │            │      │
│  ┌──────▼────────────────▼──────────────▼─────────────▼────────────▼────┐ │
│  │                         Services Layer                                │ │
│  │   storage_service │ yt_service │ whisper_service │ llm_config_service │ │
│  └──────┬──────────────────────────────────────────────────┬────────────┘ │
│         │                                                   │              │
│  ┌──────▼──────┐                                  ┌────────▼────────────┐ │
│  │  SQLite DB  │                                  │   services/llm/     │ │
│  │ + File Store│                                  │  (generic module)   │ │
│  └─────────────┘                                  │                     │ │
│                                                   │  ┌───────────────┐  │ │
│                                                   │  │  base.py      │  │ │
│                                                   │  │  registry.py  │  │ │
│                                                   │  └───────┬───────┘  │ │
│                                                   │          │          │ │
│                                          ┌────────▼──────────────────┐  │ │
│                                          │     Provider Adapters      │  │ │
│                                          │  OpenAI · Anthropic        │  │ │
│                                          │  Gemini · Ollama · vLLM    │  │ │
│                                          └────────────────────────────┘  │ │
│                                                   └─────────────────────┘ │
└───────────────────────────────────────────────────────────────────────────┘
```

---

### Backend Architecture

The backend is built on **FastAPI** with an async-first design. Each feature area lives in its own router and service module.

#### Routers

| Router | Path | Protocol | Purpose |
|---|---|---|---|
| `notes.py` | `/ws/notes/{video_id}` | WebSocket | Real-time note sync and screenshot appending |
| `transcription.py` | `/transcription/transcribe` | HTTP POST | Fetch captions or run Whisper |
| `transcription.py` | `/transcription/transcript/{id}/download` | HTTP GET | Download transcript as `.txt` or `.srt` |
| `ai.py` | `/ai/summary` | HTTP POST | Generate full summary (blocking) |
| `ai.py` | `/ai/summary/stream` | SSE | Stream summary tokens as they arrive |
| `ai.py` | `/ai/questions` | HTTP POST | Generate Q&A list (blocking) |
| `ai.py` | `/ai/questions/stream` | SSE | Stream Q&A tokens as they arrive |
| `download.py` | `/download/video` | HTTP POST | Stream video file to browser |
| `screenshot.py` | `/screenshot/capture` | HTTP POST | Accept base64 frame, save PNG, return URL |
| `screenshot.py` | `/screenshot/list/{video_id}` | HTTP GET | List screenshots for a video |
| `llm_config.py` | `/llm-config` | HTTP POST | Register a new LLM provider config |
| `llm_config.py` | `/llm-config` | HTTP GET | List all saved configs |
| `llm_config.py` | `/llm-config/active` | HTTP GET | Get the active config |
| `llm_config.py` | `/llm-config/{id}` | HTTP GET | Get one config by ID |
| `llm_config.py` | `/llm-config/{id}/activate` | HTTP PUT | Switch the active provider |
| `llm_config.py` | `/llm-config/{id}` | HTTP PATCH | Update model/key/url on a config |
| `llm_config.py` | `/llm-config/{id}` | HTTP DELETE | Remove a config |
| `llm_config.py` | `/llm-config/test` | HTTP POST | Fire a test prompt, get full response |
| `llm_config.py` | `/llm-config/test/stream` | SSE | Fire a test prompt, stream tokens |

#### Services

| Service | Responsibility |
|---|---|
| `storage_service.py` | SQLite init, CRUD for notes, transcripts, and screenshot records |
| `yt_service.py` | yt-dlp wrapper: video metadata, caption fetching, chunked video streaming |
| `whisper_service.py` | Downloads audio via yt-dlp, transcribes locally with OpenAI Whisper |
| `llm_config_service.py` | Persists LLM provider configs in DB; resolves the active client on demand |
| `llm/` | Generic multi-provider LLM package (see below) |

---

### LLM Module Architecture

The `services/llm/` package is a provider-agnostic abstraction layer. The rest of the app never imports a concrete adapter directly — it only calls `get_active_client()` from `llm_config_service.py`, which resolves the correct adapter at runtime.

```
services/llm/
├── base.py            # BaseLLMClient ABC — defines .complete() and .stream()
├── registry.py        # build_client(provider, config) factory
├── openai_client.py   # OpenAI + any OpenAI-compatible endpoint (Azure, etc.)
├── anthropic_client.py
├── gemini_client.py   # Wraps sync Gemini SDK in thread executor for async streaming
├── ollama_client.py   # Pure httpx — no Ollama SDK needed
└── vllm_client.py     # Delegates to OpenAI SDK pointed at local vLLM server
```

#### Interface contract (`base.py`)

Every provider adapter implements exactly two methods:

```python
class BaseLLMClient(ABC):

    async def complete(self, system: str, user: str, max_tokens: int = 1024) -> str:
        """Return the full completion as a single string."""

    async def stream(self, system: str, user: str, max_tokens: int = 1024) -> AsyncGenerator[str, None]:
        """Yield text chunks as they arrive from the model."""
```

#### How the factory works (`registry.py`)

```python
from services.llm.registry import build_client

client = build_client("openai", {
    "api_key": "sk-...",
    "model":   "gpt-4o-mini",
})

# Use identically regardless of provider:
text   = await client.complete(system="...", user="...")
chunks = client.stream(system="...", user="...")
```

#### Provider capability matrix

| Provider | Cloud | Local | Streaming | Extra SDK |
|---|---|---|---|---|
| OpenAI | ✅ | — | ✅ | `openai` |
| Anthropic | ✅ | — | ✅ | `anthropic` |
| Gemini | ✅ | — | ✅ (via thread) | `google-generativeai` |
| Ollama | — | ✅ | ✅ | none (uses `httpx`) |
| vLLM | — | ✅ | ✅ | `openai` (reused) |

---

### Frontend Architecture

Built with **SvelteKit**, the UI has two main routes.

**`/` — URL Input Page**
Simple landing page where the user pastes a YouTube URL. On submit, it validates the URL and navigates to `/watch?url=...`.

**`/watch` — Study View**
Split-panel layout:
- **Left panel** — Embedded YouTube `<iframe>` with a transparent `<canvas>` overlay for screenshot capture. A capture button reads the current video frame into the canvas, converts it to a base64 PNG, and POSTs it to `/screenshot/capture`. The returned URL is then sent over the WebSocket as an `append_screenshot` operation to embed the image inline in the notes.
- **Right panel** — Tabbed interface with Notes, Transcript, Summary, and Questions tabs.

**WebSocket client (`ws.ts`)**
A singleton that manages a single persistent WebSocket connection per `video_id`. It sends delta operations (`insert`, `update`, `full`, `append_screenshot`) and applies incoming deltas to the local note state. The connection auto-reconnects with exponential backoff on disconnect.

---

### Data Flow

#### Note-taking with screenshot

```
1. User clicks "Capture Screenshot"
2. Frontend draws current iframe frame onto <canvas>
3. Canvas exports as base64 PNG
4. POST /screenshot/capture  →  Backend saves PNG to disk
5. Backend returns { screenshot_url }
6. Frontend sends WS: { op: "append_screenshot", screenshot_url, video_timestamp }
7. Backend appends markdown image to note, saves to DB
8. Backend broadcasts updated note to all connected clients
9. Frontend renders updated note with embedded image
```

#### Transcription flow

```
1. User triggers "Get Transcript"
2. POST /transcription/transcribe { youtube_url }
3. Backend checks DB cache → returns immediately if cached
4. If not cached:
   a. Try fetching YouTube auto-captions via yt-dlp
   b. If no captions → download audio → run Whisper locally
5. Save transcript to DB
6. Return { segments: [{start, end, text}], full_text }
```

#### AI generation with active LLM provider

```
1. User clicks "Generate Summary"
2. POST /ai/summary/stream { video_id }
3. Backend calls llm_config_service.get_active_client()
4. Service reads active config from DB → build_client(provider, config)
5. Client streams tokens from the configured provider (OpenAI / Anthropic / etc.)
6. Tokens arrive as SSE events
7. Frontend EventSource appends tokens to the UI in real time
```

#### Registering and switching LLM providers

```
1. POST /llm-config { provider: "anthropic", model: "claude-haiku-...", api_key: "..." }
2. Backend validates the config, saves to DB, marks as active
3. All subsequent /ai/* calls automatically use the new provider
4. PUT /llm-config/{id}/activate  →  switch provider mid-session, zero restart
```

---

### Database Schema

```sql
-- Persists note content per video
CREATE TABLE notes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id   TEXT NOT NULL,
    content    TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Caches transcriptions to avoid repeated processing
CREATE TABLE transcripts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id   TEXT NOT NULL UNIQUE,
    title      TEXT,
    language   TEXT,
    source     TEXT,        -- 'captions' or 'whisper'
    full_text  TEXT,
    segments   TEXT,        -- JSON array of {start, end, text}
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Tracks saved screenshot files
CREATE TABLE screenshots (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id         TEXT NOT NULL,
    filename         TEXT NOT NULL,
    video_timestamp  REAL,
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Stores LLM provider configurations
CREATE TABLE llm_configs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,          -- human label, e.g. "My GPT-4o"
    provider   TEXT NOT NULL,          -- openai | anthropic | gemini | ollama | vllm
    model      TEXT NOT NULL,
    api_key    TEXT,                   -- NULL for local providers
    base_url   TEXT,                   -- custom endpoint; NULL for cloud providers
    extra      TEXT DEFAULT '{}',      -- JSON blob for future provider-specific fields
    is_active  INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

---

### API Reference

#### WebSocket — `/ws/notes/{video_id}`

On connect, the server sends the current note state as a `full` operation.

**Client → Server:**
```json
{ "op": "update", "video_id": "dQw4w9WgXcQ", "content": "Full note content" }
```

**Append screenshot:**
```json
{
  "op": "append_screenshot",
  "video_id": "dQw4w9WgXcQ",
  "screenshot_url": "http://localhost:8000/screenshots/abc.png",
  "timestamp": 142.5
}
```

Supported `op` values: `insert` · `update` · `delete` · `full` · `append_screenshot`

#### POST `/llm-config` — Register a provider

```json
{
  "name":       "My Local Llama",
  "provider":   "ollama",
  "model":      "llama3",
  "base_url":   "http://localhost:11434",
  "set_active": true
}
```

```json
{
  "name":       "Claude Haiku",
  "provider":   "anthropic",
  "model":      "claude-haiku-4-5-20251001",
  "api_key":    "sk-ant-...",
  "set_active": true
}
```

#### POST `/llm-config/test` — Test a config

```json
{ "prompt": "Explain recursion in one sentence." }
```

```json
{ "config_id": 3, "prompt": "Say hello in French." }
```

#### POST `/transcription/transcribe`

```json
{
  "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "language": "en",
  "use_whisper": false
}
```

#### POST `/ai/summary` and `/ai/summary/stream`

```json
{ "video_id": "dQw4w9WgXcQ" }
```

#### POST `/screenshot/capture`

```json
{
  "video_id":        "dQw4w9WgXcQ",
  "frame_data":      "data:image/png;base64,iVBORw0KGgo...",
  "video_timestamp": 142.5
}
```

#### POST `/download/video`

```json
{
  "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "format": "mp4_high"
}
```
`format` options: `mp4_high` · `mp4_low` · `audio_mp3`

Interactive API docs: `http://localhost:8000/docs`

---

## Tech Stack

### Backend

| Technology | Purpose |
|---|---|
| Python 3.11+ | Runtime |
| FastAPI | API framework, WebSocket, SSE |
| Uvicorn | ASGI server |
| aiosqlite | Async SQLite |
| Pydantic v2 | Data validation and schemas |
| yt-dlp | YouTube metadata, captions, video download |
| openai-whisper | Local speech-to-text transcription |
| openai SDK | OpenAI + vLLM adapter |
| anthropic SDK | Anthropic Claude adapter |
| google-generativeai | Google Gemini adapter |
| httpx | Ollama adapter (no Ollama SDK needed) |
| sse-starlette | Server-Sent Events for streaming |
| ffmpeg | Audio/video processing (Whisper dependency) |

### Frontend

| Technology | Purpose |
|---|---|
| SvelteKit | Full-stack framework |
| TypeScript | Type safety |
| YouTube IFrame API | Embedded video player |
| Canvas API | Screenshot capture from iframe |
| WebSocket (native) | Real-time note synchronisation |
| EventSource (native) | SSE for streaming AI responses |

---

## Prerequisites

- **Python 3.11+** — `python --version`
- **Node.js 18+** — `node --version`
- **ffmpeg** — required by Whisper for audio processing
  - macOS: `brew install ffmpeg`
  - Ubuntu/Debian: `sudo apt install ffmpeg`
  - Windows: download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH
- **Git** — `git --version`
- At least one LLM provider (see [LLM Provider Setup](#llm-provider-setup))

---

## Installation Guide

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/youtube-study-tool.git
cd youtube-study-tool
```

### 2. Backend Setup

```bash
cd backend

# Create and activate a virtual environment
python -m venv venv

# macOS / Linux:
source venv/bin/activate

# Windows:
venv\Scripts\activate

# Install all dependencies (includes all LLM provider SDKs)
pip install -r requirements.txt
```

> **Note:** If you only want specific providers, you can skip unneeded SDKs — see the commented sections in `requirements.txt`.

### 3. Frontend Setup

```bash
cd ../frontend
npm install
```

### 4. Environment Variables

```bash
cd ../backend
cp .env.example .env
```

Open `.env`:

```env
# Server
HOST=0.0.0.0
PORT=8000
BASE_URL=http://localhost:8000

# Database
DB_PATH=storage/study_tool.db

# Whisper model size (for local transcription fallback)
# Options: tiny | base | small | medium | large
WHISPER_MODEL=base
```

> LLM provider credentials are **no longer stored in `.env`** — they are registered at runtime via `POST /llm-config`. See [LLM Provider Setup](#llm-provider-setup).

### 5. Running the App

**Terminal 1 — Backend:**

```bash
cd backend
source venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 — Frontend:**

```bash
cd frontend
npm run dev
```

Open `http://localhost:5173`. API docs at `http://localhost:8000/docs`.

---

### Docker Setup

**Backend only:**

```bash
cd backend
cp .env.example .env
docker compose up --build
```

**Full stack:**

```yaml
# docker-compose.yml at repo root
services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    volumes:
      - backend_storage:/app/storage
    env_file:
      - ./backend/.env

  frontend:
    build: ./frontend
    ports:
      - "5173:5173"
    environment:
      - PUBLIC_API_URL=http://localhost:8000
    depends_on:
      - backend

volumes:
  backend_storage:
```

```bash
docker compose up --build
```

---

## LLM Provider Setup

LLM providers are registered at runtime via `POST /llm-config`. No restart needed. The `set_active: true` flag (default) immediately makes the new config the one used by all AI features.

All examples below can be sent to `http://localhost:8000/llm-config` once the backend is running, or tested interactively via `http://localhost:8000/docs`.

---

### OpenAI

Supports all OpenAI chat models and any OpenAI-compatible endpoint (Azure OpenAI, etc.).

```bash
curl -X POST http://localhost:8000/llm-config \
  -H "Content-Type: application/json" \
  -d '{
    "name":       "GPT-4o Mini",
    "provider":   "openai",
    "model":      "gpt-4o-mini",
    "api_key":    "sk-...",
    "set_active": true
  }'
```

**Azure OpenAI** — pass your deployment endpoint as `base_url`:

```json
{
  "name":     "Azure GPT-4o",
  "provider": "openai",
  "model":    "gpt-4o",
  "api_key":  "your-azure-key",
  "base_url": "https://YOUR_RESOURCE.openai.azure.com/openai/deployments/YOUR_DEPLOYMENT/",
  "set_active": true
}
```

Available models: `gpt-4o` · `gpt-4o-mini` · `gpt-4-turbo` · `gpt-3.5-turbo`

---

### Anthropic Claude

```bash
curl -X POST http://localhost:8000/llm-config \
  -H "Content-Type: application/json" \
  -d '{
    "name":       "Claude Haiku",
    "provider":   "anthropic",
    "model":      "claude-haiku-4-5-20251001",
    "api_key":    "sk-ant-...",
    "set_active": true
  }'
```

Available models: `claude-opus-4-5` · `claude-sonnet-4-5` · `claude-haiku-4-5-20251001`

Get your API key at [console.anthropic.com](https://console.anthropic.com).

---

### Google Gemini

```bash
curl -X POST http://localhost:8000/llm-config \
  -H "Content-Type: application/json" \
  -d '{
    "name":       "Gemini Flash",
    "provider":   "gemini",
    "model":      "gemini-1.5-flash",
    "api_key":    "AIza...",
    "set_active": true
  }'
```

Available models: `gemini-2.0-flash` · `gemini-1.5-pro` · `gemini-1.5-flash`

Get your API key at [aistudio.google.com](https://aistudio.google.com).

---

### Ollama (Local)

Run models entirely on your machine. No API key needed. Install Ollama from [ollama.com](https://ollama.com), then pull a model:

```bash
ollama pull llama3
ollama pull mistral
ollama pull phi3
```

Register with the backend:

```bash
curl -X POST http://localhost:8000/llm-config \
  -H "Content-Type: application/json" \
  -d '{
    "name":       "Local Llama 3",
    "provider":   "ollama",
    "model":      "llama3",
    "base_url":   "http://localhost:11434",
    "set_active": true
  }'
```

`base_url` defaults to `http://localhost:11434` if omitted. For a remote Ollama server, change the host accordingly.

---

### vLLM (Self-hosted)

vLLM serves any HuggingFace model via an OpenAI-compatible API. Start a vLLM server:

```bash
pip install vllm
vllm serve meta-llama/Meta-Llama-3-8B-Instruct --port 8001
```

Register with the backend:

```bash
curl -X POST http://localhost:8000/llm-config \
  -H "Content-Type: application/json" \
  -d '{
    "name":       "vLLM Llama 3 8B",
    "provider":   "vllm",
    "model":      "meta-llama/Meta-Llama-3-8B-Instruct",
    "base_url":   "http://localhost:8001/v1",
    "api_key":    "EMPTY",
    "set_active": true
  }'
```

`api_key` must be a non-empty string — vLLM accepts any value.

---

### Switching Providers at Runtime

List all saved configs:
```bash
curl http://localhost:8000/llm-config
```

Check the active provider:
```bash
curl http://localhost:8000/llm-config/active
```

Switch to a different saved config (no restart required):
```bash
curl -X PUT http://localhost:8000/llm-config/3/activate
```

Test any config with a quick prompt:
```bash
curl -X POST http://localhost:8000/llm-config/test \
  -H "Content-Type: application/json" \
  -d '{ "config_id": 3, "prompt": "Say hello in one sentence." }'
```

Test with streaming:
```bash
curl -N -X POST http://localhost:8000/llm-config/test/stream \
  -H "Content-Type: application/json" \
  -d '{ "prompt": "Count to five slowly." }'
```

Update a saved config (e.g. rotate an API key):
```bash
curl -X PATCH http://localhost:8000/llm-config/2 \
  -H "Content-Type: application/json" \
  -d '{ "api_key": "sk-new-key-here" }'
```

Delete a config:
```bash
curl -X DELETE http://localhost:8000/llm-config/4
```

> You cannot delete the active config. Activate another config first, then delete.

---

## Configuration

### Whisper Model Size

The `WHISPER_MODEL` environment variable controls local transcription quality:

| Model | Size | Speed | Accuracy | RAM Required |
|---|---|---|---|---|
| `tiny` | 75 MB | Fastest | Low | ~1 GB |
| `base` | 140 MB | Fast | Good | ~1 GB |
| `small` | 460 MB | Moderate | Better | ~2 GB |
| `medium` | 1.5 GB | Slow | High | ~5 GB |
| `large` | 3 GB | Slowest | Best | ~10 GB |

`base` is the default. Use `small` or `medium` for technical or non-English content.

### CORS Origins

By default the backend accepts requests from `http://localhost:5173` and `http://localhost:4173`. To add production origins, edit `allow_origins` in `main.py`.

---

## Usage Guide

1. **Start the backend and frontend** (see Installation Guide). The server auto-creates the database and screenshot directory on first run.

2. **Register an LLM provider** via `POST /llm-config` or the Swagger UI at `/docs`. Do this before using any AI features. See [LLM Provider Setup](#llm-provider-setup) for provider-specific examples.

3. **Paste a YouTube URL** on the landing page and press Enter or click "Start Studying".

4. **Watch the video** in the embedded player on the left.

5. **Take notes** in the Notes panel on the right. Notes save automatically via WebSocket every time you type.

6. **Capture a screenshot** by clicking the camera icon while the video is playing. The current frame is embedded directly into your notes at the cursor position with a timestamp label.

7. **Get the transcript** in the Transcript tab. The app first tries YouTube's own captions (instant). If none exist, it downloads the audio and runs Whisper locally (30–120 seconds depending on video length and model).

8. **Generate a summary** in the Summary tab. Tokens stream progressively from your active LLM provider.

9. **Generate questions** in the Questions tab. Ten Q&A pairs are generated from the transcript.

10. **Download the transcript** as `.txt` (plain text) or `.srt` (timestamped subtitles).

11. **Download the video** via the Download button — high MP4, low MP4, or audio-only MP3.

12. **Switch AI providers** mid-session via `PUT /llm-config/{id}/activate`. The next AI request will use the new provider automatically.

---

## Development Guide

### Running Tests

```bash
cd backend
pytest tests/ -v
```

### Adding a New LLM Provider

The generic LLM module is designed to be extended with minimal changes.

**Step 1** — Create `backend/services/llm/myprovider_client.py`:

```python
from typing import AsyncGenerator
from .base import BaseLLMClient, LLMError

class MyProviderClient(BaseLLMClient):

    def __init__(self, api_key: str, model: str = "my-default-model"):
        self.model = model
        # initialise SDK client here

    async def complete(self, system: str, user: str, max_tokens: int = 1024) -> str:
        try:
            # call your provider's API
            return "response text"
        except Exception as e:
            raise LLMError("myprovider", str(e)) from e

    async def stream(self, system: str, user: str, max_tokens: int = 1024) -> AsyncGenerator[str, None]:
        try:
            # stream tokens
            yield "chunk"
        except Exception as e:
            raise LLMError("myprovider", str(e)) from e
```

**Step 2** — Register it in `backend/services/llm/registry.py`:

```python
from .myprovider_client import MyProviderClient

# Add to the LLMProvider enum in base.py:
MYPROVIDER = "myprovider"

# Add to build_client():
if p == LLMProvider.MYPROVIDER:
    return MyProviderClient(
        api_key=config["api_key"],
        model=config.get("model", "my-default-model"),
    )
```

**Step 3** — Add to the `LLMProviderEnum` in `models/schemas.py`:

```python
class LLMProviderEnum(str, Enum):
    ...
    MYPROVIDER = "myprovider"
```

That's it. No changes needed to the router, the AI endpoints, or the config service.

### Adding a New Router

1. Create `backend/routers/my_feature.py` with an `APIRouter` instance
2. Register it in `main.py`:

```python
from routers import my_feature
app.include_router(my_feature.router, prefix="/my-feature", tags=["My Feature"])
```

### Project Conventions

- All external I/O (yt-dlp, Whisper, blocking SDK calls) is run via `asyncio.run_in_executor` to keep the event loop free.
- Database access uses `aiosqlite` throughout.
- All request/response shapes are Pydantic models in `models/schemas.py`.
- The WebSocket manager stores connections in an in-memory dict keyed by `video_id`. For multi-worker deployments, replace with a Redis pub/sub backend.
- `api_key` values are masked in all API responses (first 8 chars + `••••••••`). They are stored in plaintext in SQLite — add encryption at rest for production deployments.
- The `ai.py` router calls `get_active_client()` on every request, so provider switches via `PUT /llm-config/{id}/activate` take effect immediately without restart.

---

## Troubleshooting

**`ffmpeg not found`**
Whisper requires ffmpeg on your `PATH`. Install it with your system package manager and run `ffmpeg -version` to verify.

**`yt-dlp` fails to download or extract captions**
YouTube occasionally changes its internal API. Update yt-dlp:
```bash
pip install --upgrade yt-dlp
```

**`No active LLM configuration found` (503 error on /ai/* endpoints)**
You need to register at least one LLM provider first. Send a `POST /llm-config` request with your provider details. See [LLM Provider Setup](#llm-provider-setup).

**LLM provider returns 401 / authentication error**
Double-check your `api_key` value. You can update it without deleting the config:
```bash
curl -X PATCH http://localhost:8000/llm-config/{id} \
  -H "Content-Type: application/json" \
  -d '{ "api_key": "sk-correct-key" }'
```

**Ollama returns connection refused**
Make sure the Ollama server is running (`ollama serve`) and the `base_url` in your config matches the host and port. If Ollama is running inside Docker, use the container's service name instead of `localhost`.

**vLLM model name mismatch**
The `model` field in your config must exactly match the model name you passed to `vllm serve`. Check with:
```bash
curl http://localhost:8001/v1/models
```

**WebSocket connection drops immediately**
Verify the backend is running and that your frontend's origin is listed in `allow_origins` in `main.py`.

**Whisper transcription is very slow**
Switch to `tiny` for fastest results at lower accuracy:
```env
WHISPER_MODEL=tiny
```
Whisper automatically uses CUDA if a GPU is available — check with `nvidia-smi`.

**Screenshots appear broken in notes**
Make sure `BASE_URL` in `.env` is the publicly reachable address of your backend. If the frontend and backend are on different hosts, `localhost` will not resolve correctly in the browser.