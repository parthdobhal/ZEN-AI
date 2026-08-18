"""
Unit tests for VoiceManager.

Verified properties:
- speak() is a no-op when voice is disabled.
- speak() strips Markdown before calling the TTS engine.
- listen_and_transcribe() raises STTUnavailableError when no STT backend is set.
- listen_and_transcribe() returns the transcription on success.
- SAPITTSEngine ImportError causes automatic fallback to EdgeTTSEngine.
"""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from zen.config.settings import Settings
from zen.voice.stt.groq_whisper import STTUnavailableError
from zen.voice.voice_manager import VoiceManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_settings(**kwargs) -> Settings:
    """Create a minimal Settings object with sensible test defaults."""
    base = dict(
        voice_enabled=True,
        voice_engine="edge_tts",
        voice_name="en-US-GuyNeural",
        voice_speed="+0%",
        wake_word_enabled=False,
        wake_phrase="hey zen",
        groq_api_key=None,
        confirmation_required=True,
        workspace_path=Path("."),
        data_path=Path("."),
        ai_provider="gemini",
        ai_model="gemini-3.6-flash",
        temperature=0.7,
        gemini_api_key=None,
        openai_api_key=None,
        anthropic_api_key=None,
        ollama_base_url="http://localhost:11434",
        ollama_model="qwen2.5-coder:7b",
        auto_open_vscode=False,
        max_coding_iterations=3,
        log_level="DEBUG",
    )
    base.update(kwargs)
    return Settings.model_construct(**base)


# ---------------------------------------------------------------------------
# speak() — voice disabled
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_speak_noop_when_voice_disabled() -> None:
    """When voice_enabled=False, speak() must return without calling TTS."""
    settings = _make_settings(voice_enabled=False)

    with patch("zen.voice.voice_manager.EdgeTTSEngine") as mock_edge_cls:
        mock_tts = AsyncMock()
        mock_edge_cls.return_value = mock_tts

        vm = VoiceManager(settings=settings)
        await vm.speak("Hello, world!")

        mock_tts.speak.assert_not_called()


@pytest.mark.asyncio
async def test_speak_noop_for_blank_text() -> None:
    """speak() with empty or whitespace-only text must not call TTS."""
    settings = _make_settings(voice_enabled=True)

    with patch("zen.voice.voice_manager.EdgeTTSEngine") as mock_edge_cls:
        mock_tts = AsyncMock()
        mock_edge_cls.return_value = mock_tts

        vm = VoiceManager(settings=settings)
        await vm.speak("   ")

        mock_tts.speak.assert_not_called()


# ---------------------------------------------------------------------------
# speak() — Markdown stripping
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_speak_strips_markdown_before_tts() -> None:
    """TTS engine must receive plain text, not raw Markdown symbols."""
    settings = _make_settings(voice_enabled=True)

    captured_text: list[str] = []

    async def fake_speak(text: str) -> None:
        captured_text.append(text)

    with patch("zen.voice.voice_manager.EdgeTTSEngine") as mock_edge_cls:
        mock_tts = MagicMock()
        mock_tts.speak = AsyncMock(side_effect=fake_speak)
        mock_edge_cls.return_value = mock_tts

        vm = VoiceManager(settings=settings)
        await vm.speak("**Important:** check the `status` now.")

    assert captured_text, "TTS was never called"
    spoken = captured_text[0]
    assert "**" not in spoken
    assert "`" not in spoken
    assert "Important" in spoken
    assert "status" in spoken


# ---------------------------------------------------------------------------
# listen_and_transcribe() — no STT backend
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_listen_and_transcribe_raises_when_no_groq_key() -> None:
    """Without GROQ_API_KEY, listen_and_transcribe() must raise STTUnavailableError."""
    settings = _make_settings(groq_api_key=None)

    with patch("zen.voice.voice_manager.EdgeTTSEngine"):
        vm = VoiceManager(settings=settings)

    with pytest.raises(STTUnavailableError) as exc_info:
        await vm.listen_and_transcribe()

    assert "GROQ_API_KEY" in str(exc_info.value) or "STT" in str(exc_info.value)


# ---------------------------------------------------------------------------
# listen_and_transcribe() — success path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_listen_and_transcribe_returns_transcription() -> None:
    """Mocked audio capture + STT → correct transcription returned."""
    import struct
    import wave
    import io

    # Build minimal WAV bytes
    pcm = struct.pack("<800h", *([1000] * 800))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(pcm)
    fake_wav = buf.getvalue()

    settings = _make_settings(groq_api_key="fake-key")

    with patch("zen.voice.voice_manager.EdgeTTSEngine"), \
         patch("zen.voice.voice_manager.GroqWhisperSTT") as mock_stt_cls:

        mock_stt = MagicMock()
        mock_stt.transcribe = AsyncMock(return_value="set a timer for five minutes")
        mock_stt_cls.return_value = mock_stt

        vm = VoiceManager(settings=settings)

        with patch.object(vm.audio_capture, "listen_phrase", AsyncMock(return_value=fake_wav)):
            result = await vm.listen_and_transcribe(timeout=3.0)

    assert result == "set a timer for five minutes"


@pytest.mark.asyncio
async def test_listen_and_transcribe_returns_empty_on_silence() -> None:
    """When listen_phrase returns None (silence/timeout), result is empty string."""
    settings = _make_settings(groq_api_key="fake-key")

    with patch("zen.voice.voice_manager.EdgeTTSEngine"), \
         patch("zen.voice.voice_manager.GroqWhisperSTT"):
        vm = VoiceManager(settings=settings)

        with patch.object(vm.audio_capture, "listen_phrase", AsyncMock(return_value=None)):
            result = await vm.listen_and_transcribe()

    assert result == ""


# ---------------------------------------------------------------------------
# SAPI → EdgeTTS fallback on ImportError
# ---------------------------------------------------------------------------

def test_voice_manager_falls_back_to_edge_tts_when_pyttsx3_absent() -> None:
    """
    When the user configures voice_engine='sapi' but pyttsx3 is unavailable,
    VoiceManager must silently fall back to EdgeTTSEngine rather than crashing.
    """
    from zen.voice.tts.edge_tts_engine import EdgeTTSEngine

    settings = _make_settings(voice_engine="sapi")

    with patch("zen.voice.voice_manager.SAPITTSEngine", side_effect=ImportError("pyttsx3 missing")):
        vm = VoiceManager(settings=settings)

    assert isinstance(vm.tts, EdgeTTSEngine)
