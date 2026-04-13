"""
transcriber.py — Audio transcription via OpenAI Whisper API.
Transcribes voice messages (OGG/MP3/WAV) to text.
"""
import os
import httpx
from pathlib import Path


async def transcribe_audio(file_path: str) -> str | None:
    """
    Transcribe an audio file using OpenAI Whisper API.
    Returns transcribed text or None if transcription fails.
    """
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return None

    path = Path(file_path)
    if not path.exists():
        return None

    # Determine MIME type
    ext = path.suffix.lower()
    mime_map = {
        ".ogg": "audio/ogg",
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".m4a": "audio/mp4",
        ".webm": "audio/webm",
    }
    mime = mime_map.get(ext, "audio/ogg")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            with open(file_path, "rb") as f:
                resp = await client.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    files={"file": (path.name, f, mime)},
                    data={"model": "whisper-1", "language": "es"},
                )
            if resp.status_code == 200:
                return resp.json().get("text", "").strip()
            return None
    except Exception:
        return None
