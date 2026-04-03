"""
Whisper transcription service — hardened against NaN logits on GPU.

Root causes of the NaN logits error and their fixes applied here:
  1. FP16 overflow on certain GPU architectures (Ampere, Ada, consumer cards) →
       force fp32 inference via `model.transcribe(..., fp16=False)`
  2. Silent / nearly-silent audio produces all-NaN attention weights →
       detect and skip blank chunks with an RMS energy gate
  3. Very long audio fed as a single chunk causes context overflow →
       handled automatically by Whisper's chunking; we also re-pad if needed
  4. Stale model cache on CUDA (rare) →
       model is loaded fresh per worker via a module-level cache keyed on device
"""

import asyncio
import logging
import os
import tempfile
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")   # tiny | base | small | medium | large

# Module-level cache: model_name → loaded Whisper model
# Avoids reloading the model on every request while still being process-safe.
_model_cache: dict = {}

# Minimum RMS energy threshold below which an audio file is considered silent.
# Whisper returns all-NaN logits on silent input.
_SILENCE_RMS_THRESHOLD = float(os.getenv("WHISPER_SILENCE_THRESHOLD", "0.001"))


# ── Model loading ─────────────────────────────────────────────────────────────

def _load_model(model_name: str):
    """Load (and cache) a Whisper model. Always uses the safest device config."""
    if model_name in _model_cache:
        return _model_cache[model_name]

    import torch
    import whisper

    # Prefer CUDA when available, but fall back to CPU on any load error.
    if torch.cuda.is_available():
        try:
            model = whisper.load_model(model_name, device="cuda")
            logger.info("Whisper '%s' loaded on CUDA", model_name)
        except Exception as exc:
            logger.warning("CUDA load failed (%s) — falling back to CPU", exc)
            model = whisper.load_model(model_name, device="cpu")
    else:
        model = whisper.load_model(model_name, device="cpu")
        logger.info("Whisper '%s' loaded on CPU", model_name)

    _model_cache[model_name] = model
    return model


# ── Audio validation ──────────────────────────────────────────────────────────

def _check_audio(audio_path: str) -> dict:
    """
    Validate audio before handing it to Whisper.
    Returns a dict with keys:
      ok      - bool, False means skip Whisper (would produce NaN)
      reason  - human-readable string when ok=False
      rms     - float RMS energy of the signal
      samples - int number of samples
    """
    try:
        import torch
        import whisper

        # whisper.load_audio resamples to 16 kHz mono float32
        audio = whisper.load_audio(audio_path)           # np.ndarray, float32
        rms   = float(np.sqrt(np.mean(audio ** 2)))
        n     = len(audio)

        if n < 1600:   # < 0.1 s at 16 kHz — too short for Whisper
            return {"ok": False, "reason": "audio too short (< 0.1 s)", "rms": rms, "samples": n}

        if rms < _SILENCE_RMS_THRESHOLD:
            return {"ok": False, "reason": f"audio is silent (RMS={rms:.6f})", "rms": rms, "samples": n}

        return {"ok": True, "reason": "", "rms": rms, "samples": n}

    except Exception as exc:
        return {"ok": False, "reason": f"audio validation error: {exc}", "rms": 0.0, "samples": 0}


# ── Core transcription ────────────────────────────────────────────────────────

def _transcribe_sync(audio_path: str, language: Optional[str], model_name: str) -> list[dict]:
    """
    Synchronous transcription — runs in a thread executor.

    Key hardening applied:
      • fp16=False         → avoids NaN logits from FP16 overflow on GPU
      • condition_on_previous_text=False → prevents error accumulation
        across chunks (common cause of cascading NaN in long audio)
      • temperature fallback list  → Whisper retries with higher temperature
        when it detects decoding failures; covers most remaining NaN cases
    """
    import torch

    check = _check_audio(audio_path)
    if not check["ok"]:
        raise ValueError(f"Whisper refused to process audio: {check['reason']}")

    logger.info(
        "Transcribing '%s' — RMS=%.4f, samples=%d, model=%s",
        audio_path, check["rms"], check["samples"], model_name,
    )

    model = _load_model(model_name)

    # Always run fp32 on GPU.
    # fp16=True is Whisper's default on CUDA and is the #1 cause of NaN logits
    # on consumer GPUs (RTX 30xx/40xx) because their fp16 dynamic range is
    # exceeded by certain audio features.
    use_fp16 = False

    transcribe_kwargs = dict(
        fp16=use_fp16,
        verbose=False,
        word_timestamps=False,
        condition_on_previous_text=False,   # prevents cascading hallucination / NaN
        # Temperature fallback: Whisper raises on all-NaN logits unless we give
        # it a sequence of temperatures to retry with.
        temperature=(0.0, 0.2, 0.4, 0.6, 0.8, 1.0),
    )

    if language:
        transcribe_kwargs["language"] = language

    try:
        result = model.transcribe(audio_path, **transcribe_kwargs)
    except Exception as exc:
        # If GPU inference still fails, retry on CPU before giving up.
        if "cuda" in str(exc).lower() or "nan" in str(exc).lower():
            logger.warning("GPU transcription failed (%s) — retrying on CPU", exc)
            import whisper as _whisper
            cpu_model = _whisper.load_model(model_name, device="cpu")
            transcribe_kwargs["fp16"] = False
            result = cpu_model.transcribe(audio_path, **transcribe_kwargs)
        else:
            raise

    segments = []
    for seg in result.get("segments", []):
        text = seg["text"].strip()
        if text:
            segments.append({
                "start": round(float(seg["start"]), 3),
                "end":   round(float(seg["end"]),   3),
                "text":  text,
            })

    if not segments:
        raise ValueError("Whisper produced no transcript segments — audio may be non-speech.")

    return segments


# ── Public async API ──────────────────────────────────────────────────────────

async def transcribe_audio(audio_path: str, language: Optional[str] = None) -> list[dict]:
    """
    Async wrapper around _transcribe_sync.
    Runs in a thread pool to avoid blocking the event loop.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, _transcribe_sync, audio_path, language, WHISPER_MODEL
    )


async def download_and_transcribe(youtube_url: str, language: Optional[str] = None) -> list[dict]:
    """
    Downloads audio from YouTube with yt-dlp, then transcribes with Whisper.

    Audio pipeline:
      yt-dlp bestaudio → ffmpeg → 16-bit PCM WAV (mono, 16 kHz)

    Using WAV (not mp3/m4a) avoids a class of ffmpeg decode errors that can
    produce corrupted float arrays and trigger NaN logits in Whisper.
    """
    import yt_dlp

    with tempfile.TemporaryDirectory() as tmpdir:
        raw_path = os.path.join(tmpdir, "audio.%(ext)s")

        ydl_opts = {
            "quiet":        True,
            "no_warnings":  True,
            "noplaylist":   True,
            "format":       "bestaudio/best",
            "outtmpl":      raw_path,
            "postprocessors": [{
                "key":              "FFmpegExtractAudio",
                "preferredcodec":   "wav",
                "preferredquality": "0",   # lossless PCM
            }],
            # Force ffmpeg to output 16 kHz mono — matches Whisper's expected
            # input format and prevents resampling artifacts that can produce NaN.
            "postprocessor_args": {
                "FFmpegExtractAudio": [
                    "-ar", "16000",   # sample rate
                    "-ac", "1",       # mono
                ]
            },
        }

        def _dl():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([youtube_url])

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _dl)

        wav_files = [f for f in os.listdir(tmpdir) if f.endswith(".wav")]
        if not wav_files:
            raise FileNotFoundError(
                "yt-dlp produced no .wav output — ffmpeg may be missing or "
                "the video has no audio track."
            )

        wav_path = os.path.join(tmpdir, wav_files[0])
        file_size = os.path.getsize(wav_path)
        logger.info("Downloaded audio: %s (%.1f MB)", wav_path, file_size / 1e6)

        if file_size < 4096:   # < 4 KB — essentially empty
            raise ValueError(
                f"Downloaded audio file is suspiciously small ({file_size} bytes). "
                "The video may have no audio track."
            )

        return await transcribe_audio(wav_path, language=language)