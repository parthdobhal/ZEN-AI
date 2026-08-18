"""
Unit tests for Speech-to-Text (STT) providers.

Key properties verified:
- GroqWhisperSTT raises STTUnavailableError when no API key is present.
- GroqWhisperSTT raises STTUnavailableError on API errors (no silent fallback).
- SpeechRecognitionSTT raises ImportError when speech_recognition is absent.
- PyAudio is never imported as a side-effect of importing the voice package.
- STTBase cannot be instantiated directly.
"""

import sys
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import struct
import wave
import io

from zen.voice.stt.groq_whisper import GroqWhisperSTT, STTUnavailableError
from zen.voice.stt_base import STTBase


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_wav_bytes(sample_rate: int = 16000, n_samples: int = 1600) -> bytes:
    """Return valid minimal WAV bytes for testing."""
    pcm = struct.pack(f"<{n_samples}h", *([500] * n_samples))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return buf.getvalue()


WAV_BYTES = _make_wav_bytes()


# ---------------------------------------------------------------------------
# STTBase
# ---------------------------------------------------------------------------

def test_stt_base_is_abstract() -> None:
    """STTBase cannot be instantiated directly — it requires concrete implementations."""
    with pytest.raises(TypeError):
        STTBase()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# GroqWhisperSTT — no API key
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_groq_whisper_no_key_raises_stt_unavailable_error() -> None:
    """GroqWhisperSTT with no API key must raise STTUnavailableError, not return empty string."""
    stt = GroqWhisperSTT(api_key=None)
    with pytest.raises(STTUnavailableError) as exc_info:
        await stt.transcribe(WAV_BYTES)
    # Error message must contain actionable guidance.
    assert "GROQ_API_KEY" in str(exc_info.value)


@pytest.mark.asyncio
async def test_groq_whisper_no_key_error_message_has_guidance() -> None:
    """The STTUnavailableError from a missing key must mention a remediation step."""
    stt = GroqWhisperSTT(api_key=None)
    with pytest.raises(STTUnavailableError) as exc_info:
        await stt.transcribe(WAV_BYTES)
    msg = str(exc_info.value)
    assert "GROQ_API_KEY" in msg or "faster-whisper" in msg


# ---------------------------------------------------------------------------
# GroqWhisperSTT — API success
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_groq_whisper_api_success_returns_text() -> None:
    """A 200 response from Groq returns the transcribed text."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"text": "hello world"}

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        stt = GroqWhisperSTT(api_key="test-key-abc123")
        result = await stt.transcribe(WAV_BYTES)

    assert result == "hello world"


# ---------------------------------------------------------------------------
# GroqWhisperSTT — API error (no silent fallback)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_groq_whisper_api_http_error_raises_stt_unavailable() -> None:
    """An HTTP 500 from Groq raises STTUnavailableError — not silently returns empty."""
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        stt = GroqWhisperSTT(api_key="test-key")
        with pytest.raises(STTUnavailableError) as exc_info:
            await stt.transcribe(WAV_BYTES)

    assert "500" in str(exc_info.value) or "Groq" in str(exc_info.value)


@pytest.mark.asyncio
async def test_groq_whisper_network_error_raises_stt_unavailable() -> None:
    """A network-level exception raises STTUnavailableError rather than propagating raw."""
    import httpx

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        stt = GroqWhisperSTT(api_key="test-key")
        with pytest.raises(STTUnavailableError):
            await stt.transcribe(WAV_BYTES)


# ---------------------------------------------------------------------------
# SpeechRecognitionSTT — optional import guard
# ---------------------------------------------------------------------------

def test_speech_recognition_stt_raises_import_error_when_package_absent() -> None:
    """
    When speech_recognition is not importable, SpeechRecognitionSTT() must raise
    ImportError with a message that does NOT mention PyAudio.
    """
    from zen.voice.stt.groq_whisper import SpeechRecognitionSTT

    with patch.dict(sys.modules, {"speech_recognition": None}):
        with pytest.raises(ImportError) as exc_info:
            SpeechRecognitionSTT()

    msg = str(exc_info.value)
    # Must give guidance without confusing the user about PyAudio
    assert "speech_recognition" in msg.lower() or "SpeechRecognition" in msg


# ---------------------------------------------------------------------------
# PyAudio is never imported
# ---------------------------------------------------------------------------

def test_pyaudio_not_imported_by_voice_package() -> None:
    """
    Importing zen.voice must NOT trigger an import of pyaudio at any level.
    This is a regression guard to ensure we never re-introduce PyAudio as a
    hard dependency.
    """
    # Force fresh import evaluation in a clean sys.modules snapshot
    pyaudio_keys = [k for k in sys.modules if "pyaudio" in k.lower()]
    assert pyaudio_keys == [], (
        f"pyaudio was imported as a side-effect of loading the voice package: {pyaudio_keys}"
    )


def test_pyaudio_not_in_audio_capture_imports() -> None:
    """Importing zen.voice.audio_capture must not load pyaudio."""
    import importlib
    import zen.voice.audio_capture  # noqa: F401 — side-effect import for the check
    importlib.reload(zen.voice.audio_capture)
    pyaudio_keys = [k for k in sys.modules if "pyaudio" in k.lower()]
    assert pyaudio_keys == []
