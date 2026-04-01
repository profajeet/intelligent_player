import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from routers import notes, transcription, ai, download, screenshot
from services.storage_service import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    os.makedirs("storage/screenshots", exist_ok=True)
    yield


app = FastAPI(
    title="YouTube Study Tool API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:4173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/screenshots", StaticFiles(directory="storage/screenshots"), name="screenshots")

app.include_router(notes.router,         prefix="/ws",           tags=["Notes (WebSocket)"])
app.include_router(transcription.router, prefix="/transcription", tags=["Transcription"])
app.include_router(ai.router,            prefix="/ai",            tags=["AI Generation"])
app.include_router(download.router,      prefix="/download",      tags=["Download"])
app.include_router(screenshot.router,    prefix="/screenshot",    tags=["Screenshot"])


@app.get("/health")
async def health():
    return {"status": "ok"}
