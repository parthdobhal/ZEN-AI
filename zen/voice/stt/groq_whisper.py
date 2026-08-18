"""
Speech-to-Text Providers (Groq Cloud Whisper & optional Google Fallback).

Design notes:
- PyAudio is NOT imported anywhere in this module.
- The ``SpeechRecognition`` library (``speech_recognition``) is lazy-imported
  only inside ``SpeechRecognitionSTT.__init__`` to ensure it is never a hard
  dependency.  If it is absent the class raises ``ImportError`` with guidance.
- ``GroqWhisperSTT`` raises ``STTUnavailableError`` when no API key is
  configured, giving the user an actionable error instead of a silent failure.
"""

import io
from pathlib import Path
import httpx

from zen.core.logger import logger
from zen.voice.stt_base import STTBase


class STTUnavailableError(RuntimeError):
    """Raised when no speech-to-text backend is available or configured."""

    DEFAULT_MESSAGE = (
        "No STT backend is available. "
        "Set GROQ_API_KEY in your .env file to enable Groq Whisper, "
        "or install faster-whisper for fully offline transcription: "
        "pip install faster-whisper"
    )


class SpeechRecognitionSTT(STTBase):
    """
    Optional Google Web Speech API transcription using SpeechRecognition.

    This class is **not** selected automatically.  It is available only for
    users who explicitly opt-in by installing ``speech_recognition``.
    PyAudio is NOT used: audio bytes are read from a WAV buffer, never
    from a live microphone stream through this library.

    Raises:
        ImportError: If the ``speech_recognition`` package is not installed.
    """

    name = "speech_recognition"

    def __init__(self) -> None:
        try:
            import speech_recognition as sr  # noqa: PLC0415  (lazy import by design)
        except ImportError as exc:
            raise ImportError(
                "The 'speech_recognition' package is not installed. "
                "Install it with: pip install SpeechRecognition\n"
                "Note: PyAudio is NOT required for ZEN's audio capture "
                "(sounddevice is used instead)."
            ) from exc
        self._sr = sr
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 300
        self.recognizer.dynamic_energy_threshold = True

    async def transcribe(self, audio_data: bytes) -> str:
        """Transcribe PCM/WAV audio bytes via Google Web Speech API."""
        sr = self._sr
        try:
            audio_file = io.BytesIO(audio_data)
            with sr.AudioFile(audio_file) as source:
                audio = self.recognizer.record(source)
                return self.recognizer.recognize_google(audio)
        except sr.UnknownValueError:
            return ""
        except Exception as e:
            logger.debug(f"STT transcription error: {e}")
            return ""

    async def transcribe_file(self, audio_file_path: Path) -> str:
        sr = self._sr
        try:
            with sr.AudioFile(str(audio_file_path)) as source:
                audio = self.recognizer.record(source)
                return self.recognizer.recognize_google(audio)
        except Exception as e:
            logger.debug(f"STT file error: {e}")
            return ""


class GroqWhisperSTT(STTBase):
    """Ultra-fast cloud Whisper transcription using Groq API."""

    name = "groq_whisper"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key
        self.base_url = "https://api.groq.com/openai/v1/audio/transcriptions"

    async def transcribe(self, audio_data: bytes) -> str:
        """
        Transcribe WAV audio bytes using the Groq Whisper API.

        Raises:
            STTUnavailableError: If no API key is configured, or if the
                Groq API returns an error.  No silent fallback is attempted
                so the caller always receives a clear, actionable failure.
        """
        if not self.api_key:
            raise STTUnavailableError(STTUnavailableError.DEFAULT_MESSAGE)

        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            files = {"file": ("audio.wav", audio_data, "audio/wav")}
            data = {"model": "whisper-large-v3"}

            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(self.base_url, headers=headers, files=files, data=data)
                if res.status_code == 200:
                    return res.json().get("text", "").strip()
                else:
                    logger.debug(f"Groq STT error ({res.status_code}): {res.text}")
                    raise STTUnavailableError(
                        f"Groq Whisper API returned HTTP {res.status_code}. "
                        "Check your GROQ_API_KEY or network connection."
                    )
        except STTUnavailableError:
            raise
        except Exception as e:
            logger.debug(f"Groq STT failed: {e}")
            raise STTUnavailableError(
                f"Groq Whisper transcription failed: {e}. "
                "Check your network connection or GROQ_API_KEY."
            ) from e

    async def transcribe_file(self, audio_file_path: Path) -> str:
        with open(audio_file_path, "rb") as f:
            return await self.transcribe(f.read())
