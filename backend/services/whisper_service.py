import asyncio
import os
import tempfile
from typing import Optional

WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")   # tiny | base | small | medium | large


async def transcribe_audio(audio_path: str, language: Optional[str] = None) -> list[dict]:
    """
    Run OpenAI Whisper on a local audio file.
    Returns list of {start, end, text} segments.
    """
    import whisper

    def _run():
        model = whisper.load_model(WHISPER_MODEL)
        result = model.transcribe(
            audio_path,
            language=language,
            verbose=False,
            word_timestamps=False,
        )
        segments = []
        for seg in result.get("segments", []):
            segments.append({
                "start": round(seg["start"], 3),
                "end":   round(seg["end"],   3),
                "text":  seg["text"].strip(),
            })
        return segments

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _run)


async def download_and_transcribe(youtube_url: str, language: Optional[str] = None) -> list[dict]:
    """
    Downloads audio from a YouTube URL, then transcribes with Whisper.
    Returns list of {start, end, text} segments.
    """
    import yt_dlp

    with tempfile.TemporaryDirectory() as tmpdir:
        audio_path = os.path.join(tmpdir, "audio.%(ext)s")

        opts = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "format": "bestaudio/best",
            "outtmpl": audio_path,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "192",
            }],
        }

        def _dl():
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([youtube_url])

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _dl)

        files = [f for f in os.listdir(tmpdir) if f.endswith(".wav")]
        if not files:
            raise FileNotFoundError("Audio download produced no .wav file")

        wav_path = os.path.join(tmpdir, files[0])
        return await transcribe_audio(wav_path, language=language)
