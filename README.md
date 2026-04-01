# intelligent_player:  AI-Powered YouTube Learning Platform

A full-stack application that transforms YouTube videos into an interactive learning experience with real-time notes, screenshots, AI-generated summaries, questions, and transcription.

---

## 🚀 Features

### 🎬 Video Interaction
- Paste YouTube video link
- Watch video directly inside the app
- Timestamp-aware interactions

### 📝 Real-Time Notes
- Create and edit notes while watching
- Auto-sync notes in real-time (WebSocket)
- Timestamp-based note linking

### 📸 Screenshot Capture
- Capture frames from video at any timestamp
- Automatically embed screenshots into notes

### 🤖 AI Features
- Generate video summaries
- Generate conceptual & MCQ questions
- Extract key insights

### 🎙️ Transcription
- View full transcription of video
- Download transcription

### ⬇️ Downloads
- Download video
- Download transcription

---

## 🏗️ Architecture Overview

Frontend (SvelteKit)
        ↓
   API + WebSocket
        ↓
Backend (FastAPI)
        ↓
Services Layer (AI + Video Processing)
        ↓
Database + Storage

---

## 📁 Project Structure

project-root/
│
├── frontend/                  # SvelteKit App
├── backend/                  # FastAPI Backend
├── shared/                   # Shared configs/types (optional)
├── docker-compose.yml
└── README.md

---

## 🧑‍💻 Tech Stack

### Frontend
- SvelteKit
- TypeScript
- WebSocket client
- TipTap (rich text editor)

### Backend
- FastAPI (Python)
- WebSockets
- yt-dlp (video processing)
- ffmpeg (screenshot extraction)
- Whisper / LLM APIs (AI features)

### Storage
- PostgreSQL (metadata)
- Local / S3 (media storage)

---

## 🔌 API Endpoints

### Video
POST /video/load

### Notes
GET  /notes/{video_id}
POST /notes/save

### AI
POST /ai/summary
POST /ai/questions

### Transcription
GET /transcription/{video_id}
GET /transcription/download

### Download
GET /download/video
GET /download/transcript

---

## ⚡ WebSocket Endpoints

/ws/notes/{video_id}

Used for:
- Real-time note syncing
- Screenshot insertion
- Multi-session collaboration

---

## 🔄 Core Workflows

### 📝 Real-Time Notes
1. User types notes
2. Sent via WebSocket
3. Backend broadcasts updates
4. Persisted asynchronously

### 📸 Screenshot Flow
1. User clicks screenshot
2. Timestamp sent to backend
3. Frame extracted using ffmpeg
4. Image stored and returned
5. Inserted into notes

### 🤖 AI Processing
1. User triggers AI feature
2. Backend fetches transcript
3. AI model processes content
4. Response sent to frontend

---

## 🗄️ Database Schema (Simplified)

### videos
- id
- youtube_url
- title
- duration

### notes
- id
- video_id
- content (rich text JSON)

### screenshots
- id
- video_id
- timestamp
- image_url

---

## 🧠 Services

- YouTube Service → video metadata & download
- Transcription Service → captions / speech-to-text
- Screenshot Service → frame extraction
- AI Services → summary, questions
- Realtime Engine → WebSocket manager

---

## 🐳 Running with Docker

docker-compose up --build

---

## ⚙️ Local Development Setup

### 1. Clone Repository
git clone <repo-url>
cd project-root

### 2. Backend Setup
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload

### 3. Frontend Setup
cd frontend
npm install
npm run dev

---

## 🔧 Environment Variables

Create `.env` files in both frontend and backend:

### Backend
DATABASE_URL=
OPENAI_API_KEY=
STORAGE_PATH=

### Frontend
VITE_API_URL=http://localhost:8000

---

## 📈 Scaling Considerations

- Redis for caching & pub/sub
- Background workers (Celery / RQ)
- CDN for media delivery
- Async processing for heavy tasks

---

## 🧩 Future Enhancements

- Multi-user collaboration
- AI-assisted note suggestions
- Timeline-based annotations
- Semantic search in notes (vector DB)
- Personalized learning insights

---

## 🤝 Contributing

Contributions are welcome! Please open an issue or submit a pull request.

---

## 📄 License

MIT License

---

## 💡 Vision

This project aims to redefine how people learn from videos by combining:
- Real-time interaction
- AI-driven insights
- Structured knowledge extraction
