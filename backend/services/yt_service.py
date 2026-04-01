import asyncio
import json
import os
import re
import tempfile
from typing import Optional

YDL_BASE_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "noplaylist": True,
}


def extract_video_id(url: str) -> Optional[str]:
    patterns = [
        r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})",
        r"(?:embed/)([A-Za-z0-9_-]{11})",
        r"^([A-Za-z0-9_-]{11})$",
    ]
    for pat in patterns:
        m = re.search(pat, url)
        if m:
            return m.group(1)
    return None


async def _run_ydl(opts: dict, url: str) -> dict:
    """Run yt-dlp in a thread pool to avoid blocking the event loop."""
    import yt_dlp

    def _extract():
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _extract)


async def get_video_info(url: str) -> dict:
    opts = {**YDL_BASE_OPTS, "skip_download": True}
    info = await _run_ydl(opts, url)
    return {
        "video_id": info.get("id"),
        "title":    info.get("title"),
        "duration": info.get("duration"),
        "thumbnail": info.get("thumbnail"),
    }


async def get_captions(url: str, language: str = "en") -> Optional[list[dict]]:
    """
    Returns a list of {start, end, text} dicts if YouTube captions exist,
    otherwise returns None.
    """
    import yt_dlp

    opts = {
        **YDL_BASE_OPTS,
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": [language, f"{language}-orig"],
        "subtitlesformat": "json3",
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        opts["outtmpl"] = os.path.join(tmpdir, "%(id)s.%(ext)s")

        def _dl():
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                return info

        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(None, _dl)

        # Look for downloaded subtitle file
        for fname in os.listdir(tmpdir):
            if fname.endswith(".json3"):
                with open(os.path.join(tmpdir, fname)) as f:
                    data = json.load(f)
                return _parse_json3(data)

        # Also check .vtt fallback
        for fname in os.listdir(tmpdir):
            if fname.endswith(".vtt"):
                with open(os.path.join(tmpdir, fname)) as f:
                    return _parse_vtt(f.read())

    return None


def _parse_json3(data: dict) -> list[dict]:
    segments = []
    for event in data.get("events", []):
        if "segs" not in event:
            continue
        start = event.get("tStartMs", 0) / 1000
        dur   = event.get("dDurationMs", 0) / 1000
        text  = "".join(s.get("utf8", "") for s in event["segs"]).strip()
        if text:
            segments.append({"start": start, "end": start + dur, "text": text})
    return segments


def _parse_vtt(vtt: str) -> list[dict]:
    segments = []
    lines = vtt.strip().splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if "-->" in line:
            parts = line.split("-->")
            start = _vtt_time(parts[0].strip())
            end   = _vtt_time(parts[1].strip().split()[0])
            i += 1
            text_lines = []
            while i < len(lines) and lines[i].strip():
                text_lines.append(lines[i].strip())
                i += 1
            text = " ".join(text_lines)
            if text:
                segments.append({"start": start, "end": end, "text": text})
        else:
            i += 1
    return segments


def _vtt_time(t: str) -> float:
    parts = t.replace(",", ".").split(":")
    if len(parts) == 3:
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + float(s)
    m, s = parts
    return int(m) * 60 + float(s)


async def download_video_stream(url: str, fmt: str = "mp4_high"):
    """
    Yields chunks of the video file for streaming to the client.
    fmt: 'mp4_high' | 'mp4_low' | 'audio_mp3'
    """
    import yt_dlp

    format_map = {
        "mp4_high":  "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "mp4_low":   "worstvideo[ext=mp4]+worstaudio/worst[ext=mp4]/worst",
        "audio_mp3": "bestaudio/best",
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        outtmpl = os.path.join(tmpdir, "video.%(ext)s")

        opts = {
            **YDL_BASE_OPTS,
            "format":  format_map.get(fmt, format_map["mp4_high"]),
            "outtmpl": outtmpl,
        }

        if fmt == "audio_mp3":
            opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }]

        def _dl():
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _dl)

        files = os.listdir(tmpdir)
        if not files:
            raise FileNotFoundError("yt-dlp produced no output file")

        fpath = os.path.join(tmpdir, files[0])
        with open(fpath, "rb") as f:
            while chunk := f.read(1024 * 256):  # 256 KB chunks
                yield chunk


async def get_video_title(url: str) -> str:
    info = await get_video_info(url)
    return info.get("title", "video")
