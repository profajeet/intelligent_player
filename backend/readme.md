# YouTube Study Tool

A full-stack application that transforms any YouTube video into an interactive study session. Watch videos, take real-time notes, capture screenshots directly into your notes, generate AI summaries and questions, download videos, and get full transcriptions — all in one place.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
  - [Repository Structure](#repository-structure)
  - [System Architecture Diagram](#system-architecture-diagram)
  - [Backend Architecture](#backend-architecture)
  - [Frontend Architecture](#frontend-architecture)
  - [Data Flow](#data-flow)
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
- [Configuration](#configuration)
- [Usage Guide](#usage-guide)
- [Development Guide](#development-guide)
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

---

## Architecture

### Repository Structure

```
youtube-study-tool/
│
├── frontend/                        # SvelteKit application
│   ├── src/
│   │   ├── routes/
│   │   │   ├── +page.svelte         # Landing page — YouTube URL input
│   │   │   └── watch/
│   │   │       └── +page.svelte     # Main study view (player + panels)
│   │   └── lib/
│   │       ├── components/
│   │       │   ├── VideoPlayer.svelte
│   │       │   ├── NotesPanel.svelte
│   │       │   ├── TranscriptPanel.svelte
│   │       │   ├── ScreenshotCapture.svelte
│   │       │   ├── SummaryView.svelte
│   │       │   └── QuestionsView.svelte
│   │       └── ws.ts                # WebSocket client singleton
│   ├── package.json
│   └── svelte.config.js
│
├── backend/                         # FastAPI application
│   ├── main.py                      # App entry — CORS, router registration, lifespan
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── requirements.txt
│   ├── .env.example
│   │
│   ├── models/
│   │   └── schemas.py               # All Pydantic request/response models
│   │
│   ├── routers/
│   │   ├── notes.py                 # WS /ws/notes/{video_id}
│   │   ├── transcription.py         # POST /transcription/transcribe
│   │   ├── ai.py                    # POST /ai/summary, /ai/questions
│   │   ├── download.py              # POST /download/video
│   │   └── screenshot.py            # POST /screenshot/capture
│   │
│   ├── services/
│   │   ├── storage_service.py       # SQLite: init, CRUD for notes/transcripts/screenshots
│   │   ├── yt_service.py            # yt-dlp: metadata, captions, video streaming
│   │   ├── whisper_service.py       # OpenAI Whisper: download audio + transcribe
│   │   └── llm_service.py           # OpenAI API: summary + Q&A (streaming SSE)
│   │
│   └── storage/
│       ├── study_tool.db            # SQLite database (auto-created)
│       └── screenshots/             # Saved screenshot PNGs (auto-created)
│
├── docker-compose.yml               # Root-level compose for full-stack dev
└── README.md
```

---

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Browser (User)                                │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    SvelteKit Frontend                        │    │
│  │                                                              │    │
│  │   ┌──────────────┐   ┌────────────┐   ┌─────────────────┐  │    │
│  │   │ Video Player │   │Notes Panel │   │Transcript Panel │  │    │
│  │   │  (YouTube    │   │ (realtime  │   │  (timestamped)  │  │    │
│  │   │   iframe)    │   │  WebSocket)│   │                 │  │    │
│  │   └──────┬───────┘   └─────┬──────┘   └────────┬────────┘  │    │
│  │          │                 │                    │           │    │
│  │   ┌──────▼───────┐   ┌─────▼──────┐   ┌────────▼────────┐  │    │
│  │   │  Screenshot  │   │  Summary   │   │   Questions     │  │    │
│  │   │  (Canvas API)│   │  (SSE)     │   │   (SSE)         │  │    │
│  │   └──────┬───────┘   └─────┬──────┘   └────────┬────────┘  │    │
│  └──────────┼─────────────────┼────────────────────┼───────────┘    │
│             │   REST / WS / SSE│                    │               │
└─────────────┼─────────────────┼────────────────────┼───────────────┘
              │                 │                     │
              ▼                 ▼                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       FastAPI Backend                                │
│                                                                      │
│  ┌───────────────┐  ┌──────────────┐  ┌──────────┐  ┌───────────┐  │
│  │ /ws/notes     │  │/transcription│  │/ai/      │  │/download  │  │
│  │ (WebSocket)   │  │/screenshot   │  │summary   │  │/video     │  │
│  │               │  │              │  │/questions│  │           │  │
│  └───────┬───────┘  └──────┬───────┘  └────┬─────┘  └─────┬─────┘  │
│          │                 │               │               │        │
│  ┌───────▼─────────────────▼───────────────▼───────────────▼──────┐ │
│  │                       Services Layer                            │ │
│  │  storage_service │ yt_service │ whisper_service │ llm_service   │ │
│  └───────┬──────────────────┬──────────────────────────────────────┘ │
│          │                  │                                        │
│  ┌───────▼──────┐   ┌───────▼───────────────────────────────────┐   │
│  │   SQLite DB  │   │           External Services                │   │
│  │  + File Store│   │  YouTube · yt-dlp · Whisper · OpenAI API  │   │
│  └──────────────┘   └───────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
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

#### Services

| Service | Responsibility |
|---|---|
| `storage_service.py` | SQLite database init, note CRUD, transcript CRUD, screenshot records |
| `yt_service.py` | yt-dlp wrapper: video info, caption fetching, chunked video streaming |
| `whisper_service.py` | Downloads audio via yt-dlp, transcribes with OpenAI Whisper locally |
| `llm_service.py` | Calls OpenAI API for summary and Q&A generation, supports token streaming |

#### Database Schema (SQLite)

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
    source     TEXT,       -- 'captions' or 'whisper'
    full_text  TEXT,
    segments   TEXT,       -- JSON array of {start, end, text}
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
```

---

### Frontend Architecture

Built with **SvelteKit**, the UI has two main routes:

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

#### Note-taking with Screenshot

```
1. User clicks "Capture Screenshot"
2. Frontend draws current iframe frame onto <canvas>
3. Canvas exports as base64 PNG
4. POST /screenshot/capture  →  Backend saves PNG to disk
5. Backend returns { screenshot_url }
6. Frontend sends WS message: { op: "append_screenshot", screenshot_url, video_timestamp }
7. Backend appends markdown image to note, saves to DB
8. Backend broadcasts updated note to all connected clients
9. Frontend renders updated note content with embedded image
```

#### Transcription Flow

```
1. User triggers "Get Transcript"
2. POST /transcription/transcribe { youtube_url }
3. Backend checks DB cache → returns immediately if cached
4. If not cached:
   a. Try fetching YouTube auto-captions via yt-dlp
   b. If no captions → download audio → run Whisper locally
5. Save transcript to DB
6. Return { segments: [{start, end, text}], full_text }
7. Frontend renders scrollable, timestamped transcript
```

#### AI Generation Flow (Streaming)

```
1. User clicks "Generate Summary" or "Generate Questions"
2. POST /ai/summary/stream or /ai/questions/stream
3. Backend fetches transcript from DB (or uses provided text)
4. Backend opens streaming request to OpenAI API
5. Tokens stream back as Server-Sent Events
6. Frontend EventSource receives tokens and appends them to the UI in real time
```

---

### API Reference

#### WebSocket — `/ws/notes/{video_id}`

On connect, the server sends the current note state as a `full` operation.

**Client → Server message:**
```json
{
  "op": "update",
  "video_id": "dQw4w9WgXcQ",
  "content": "Full note content as string"
}
```

**Client → Server (append screenshot):**
```json
{
  "op": "append_screenshot",
  "video_id": "dQw4w9WgXcQ",
  "screenshot_url": "http://localhost:8000/screenshots/abc123.png",
  "timestamp": 142.5
}
```

**Supported `op` values:** `insert` · `update` · `delete` · `full` · `append_screenshot`

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
{
  "video_id": "dQw4w9WgXcQ",
  "transcript": "optional — fetched from DB if omitted",
  "language": "en"
}
```

#### POST `/screenshot/capture`
```json
{
  "video_id": "dQw4w9WgXcQ",
  "frame_data": "data:image/png;base64,iVBORw0KGgo...",
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

Interactive API docs are available at `http://localhost:8000/docs` when the backend is running.

---

## Tech Stack

### Backend
| Technology | Purpose |
|---|---|
| Python 3.11+ | Runtime |
| FastAPI | API framework, WebSocket, SSE |
| Uvicorn | ASGI server |
| aiosqlite | Async SQLite |
| Pydantic v2 | Data validation & schemas |
| yt-dlp | YouTube metadata, captions, video download |
| openai-whisper | Local speech-to-text transcription |
| openai (Python SDK) | LLM API for summary and Q&A |
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

Make sure the following are installed before proceeding:

- **Python 3.11+** — `python --version`
- **Node.js 18+** — `node --version`
- **ffmpeg** — required by Whisper for audio processing
  - macOS: `brew install ffmpeg`
  - Ubuntu/Debian: `sudo apt install ffmpeg`
  - Windows: download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH
- **Git** — `git --version`
- **An OpenAI API key** — get one at [platform.openai.com](https://platform.openai.com)

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

# On macOS/Linux:
source venv/bin/activate

# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

> **Note:** The first run will download the Whisper model weights (the `base` model is ~140 MB). This is a one-time download.

### 3. Frontend Setup

```bash
cd ../frontend

# Install Node dependencies
npm install
```

### 4. Environment Variables

```bash
cd ../backend

# Copy the example env file
cp .env.example .env
```

Open `.env` and fill in your values:

```env
# Server
HOST=0.0.0.0
PORT=8000
BASE_URL=http://localhost:8000

# Database
DB_PATH=storage/study_tool.db

# OpenAI — required for summary and questions features
OPENAI_API_KEY=sk-your-key-here
LLM_MODEL=gpt-4o-mini       # or gpt-4o, gpt-3.5-turbo

# Whisper model size
# Larger = more accurate but slower and more RAM
# Options: tiny (75MB) | base (140MB) | small (460MB) | medium (1.5GB) | large (3GB)
WHISPER_MODEL=base
```

### 5. Running the App

**Terminal 1 — Start the backend:**

```bash
cd backend
source venv/bin/activate   # if not already active
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 — Start the frontend:**

```bash
cd frontend
npm run dev
```

Open your browser at `http://localhost:5173`.

The FastAPI interactive docs are available at `http://localhost:8000/docs`.

---

### Docker Setup

The easiest way to run the backend is with Docker. You still need `ffmpeg` available on the host or inside the container (the Dockerfile installs it automatically).

**Backend only:**

```bash
cd backend
cp .env.example .env    # fill in OPENAI_API_KEY
docker compose up --build
```

**Full stack (backend + frontend):**

Create a `docker-compose.yml` at the repo root:

```yaml
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

## Configuration

### Whisper Model Size

The `WHISPER_MODEL` environment variable controls the trade-off between transcription speed and accuracy:

| Model | Size | Speed | Accuracy | RAM Required |
|---|---|---|---|---|
| `tiny` | 75 MB | Fastest | Low | ~1 GB |
| `base` | 140 MB | Fast | Good | ~1 GB |
| `small` | 460 MB | Moderate | Better | ~2 GB |
| `medium` | 1.5 GB | Slow | High | ~5 GB |
| `large` | 3 GB | Slowest | Best | ~10 GB |

For most use cases, `base` is a good default. Switch to `small` or `medium` for better accuracy on technical or non-English content.

### LLM Model

Change `LLM_MODEL` in `.env` to any OpenAI chat model:

- `gpt-4o-mini` — recommended default (fast, cheap, good quality)
- `gpt-4o` — best quality, higher cost
- `gpt-3.5-turbo` — cheapest option

### CORS Origins

By default, the backend allows requests from `http://localhost:5173` and `http://localhost:4173` (SvelteKit dev and preview). To add production origins, edit the `allow_origins` list in `main.py` or move them to a `ALLOWED_ORIGINS` env variable.

---

## Usage Guide

1. **Paste a YouTube URL** on the landing page and press Enter or click "Start Studying".

2. **Watch the video** in the embedded player on the left side of the screen.

3. **Take notes** in the Notes panel on the right. Notes are saved automatically via WebSocket every time you type.

4. **Capture a screenshot** by clicking the camera icon while the video is playing. The current frame is captured and embedded directly into your notes at the cursor position, with a timestamp label.

5. **Get the transcript** by clicking "Transcribe" in the Transcript tab. The app will first try YouTube's own captions (instant). If none exist, it downloads the audio and runs Whisper locally (takes 30–120 seconds depending on video length and model size).

6. **Generate a summary** in the Summary tab. Tokens stream in progressively — you don't have to wait for the full response.

7. **Generate questions** in the Questions tab. Ten Q&A pairs are generated from the transcript.

8. **Download the transcript** as a `.txt` file (plain text) or `.srt` file (subtitle format with timestamps).

9. **Download the video** via the Download button. Choose between high-quality MP4, low-quality MP4, or audio-only MP3.

---

## Development Guide

### Running Tests

```bash
cd backend
pytest tests/ -v
```

### Adding a New Router

1. Create `backend/routers/my_feature.py`
2. Define an `APIRouter` instance and your endpoints
3. Register it in `main.py`:

```python
from routers import my_feature
app.include_router(my_feature.router, prefix="/my-feature", tags=["My Feature"])
```

### Project Conventions

- All external I/O (yt-dlp, Whisper) is run via `asyncio.run_in_executor` to keep the event loop non-blocking.
- Database access uses `aiosqlite` for async reads/writes.
- All request/response shapes are defined as Pydantic models in `models/schemas.py`.
- The WebSocket manager (`routers/notes.py`) stores active connections in an in-memory dict keyed by `video_id`. For multi-worker deployments, replace this with a Redis pub/sub backend.

---

## Troubleshooting

**`ffmpeg not found` error**
Whisper requires ffmpeg. Install it with your system package manager (see Prerequisites) and make sure it is available on your `PATH`. Run `ffmpeg -version` to verify.

**`yt-dlp` fails to download or extract captions**
YouTube occasionally changes its internal API. Update yt-dlp to the latest version:
```bash
pip install --upgrade yt-dlp
```

**WebSocket connection drops immediately**
Check that the backend is running and that the `ALLOWED_ORIGINS` in `main.py` includes the origin your frontend is served from.

**Whisper transcription is very slow**
Switch to the `tiny` model for faster (but less accurate) results:
```env
WHISPER_MODEL=tiny
```
Or use a machine with a GPU — Whisper automatically uses CUDA if available.

**OpenAI API errors (429 / quota exceeded)**
Check your OpenAI usage and billing at [platform.openai.com](https://platform.openai.com). Consider switching to `gpt-4o-mini` which has much higher rate limits.

**Screenshots appear broken in notes**
Make sure `BASE_URL` in `.env` is set to the publicly reachable address of your backend, not just `localhost`, if the frontend is on a different host.