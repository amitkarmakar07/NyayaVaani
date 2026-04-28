"""
Whisper STT — Voice to Text
Supports Hindi + English audio input
"""

import io
from typing import Optional
from loguru import logger
from openai import OpenAI
from config import config


client = OpenAI(api_key=config.OPENAI_API_KEY)


def transcribe_audio(audio_bytes: bytes, language: Optional[str] = None) -> dict:
    """
    Transcribe audio bytes to text using Whisper.
    
    Args:
        audio_bytes: Raw audio bytes (wav/mp3/webm)
        language: Optional ISO language code ('hi' for Hindi, 'en' for English)
                  If None, Whisper auto-detects
    
    Returns:
        dict with 'text', 'language', 'success'
    """
    try:
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "complaint.webm"

        params = {
            "model": config.WHISPER_MODEL,
            "file": audio_file,
            "response_format": "verbose_json"
        }

        if language:
            params["language"] = language

        response = client.audio.transcriptions.create(**params)

        detected_language = getattr(response, "language", "unknown")
        text = response.text.strip()

        logger.success(f"Transcription done. Language: {detected_language} | Text: {text[:80]}...")

        return {
            "success": True,
            "text": text,
            "language": detected_language,
            "error": None
        }

    except Exception as e:
        logger.error(f"Whisper transcription failed: {e}")
        return {
            "success": False,
            "text": "",
            "language": "unknown",
            "error": str(e)
        }