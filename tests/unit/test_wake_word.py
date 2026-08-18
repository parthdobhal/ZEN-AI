"""
Unit tests for WakeWordDetector.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from zen.voice.wake_word import WakeWordDetector
from zen.voice.stt_base import STTBase


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _MockSTT(STTBase):
    """Minimal in-process STT stub that returns a preset string."""

    name = "mock_stt"

    def __init__(self, response: str) -> None:
        self._response = response

    async def transcribe(self, audio_data: bytes) -> str:
        return self._response

    async def transcribe_file(self, audio_file_path) -> str:  # type: ignore[override]
        return self._response


# ---------------------------------------------------------------------------
# check_text_for_wake_phrase
# ---------------------------------------------------------------------------

def test_wake_phrase_match_returns_true_and_remainder() -> None:
    detector = WakeWordDetector(wake_phrase="hey zen")
    found, remainder = detector.check_text_for_wake_phrase("hey zen turn off lights")
    assert found is True
    assert remainder.strip() == "turn off lights"


def test_wake_phrase_at_end_returns_empty_remainder() -> None:
    detector = WakeWordDetector(wake_phrase="hey zen")
    found, remainder = detector.check_text_for_wake_phrase("please hey zen")
    assert found is True
    assert remainder.strip() == "please"


def test_wake_phrase_only_returns_empty_remainder() -> None:
    detector = WakeWordDetector(wake_phrase="hey zen")
    found, remainder = detector.check_text_for_wake_phrase("hey zen")
    assert found is True
    assert remainder.strip() == ""


def test_wake_phrase_no_match_returns_false() -> None:
    detector = WakeWordDetector(wake_phrase="hey zen")
    found, remainder = detector.check_text_for_wake_phrase("hello there")
    assert found is False
    assert remainder == "hello there"


def test_wake_phrase_case_insensitive() -> None:
    detector = WakeWordDetector(wake_phrase="hey zen")
    found, _ = detector.check_text_for_wake_phrase("HEY ZEN do something")
    assert found is True


def test_wake_phrase_partial_word_not_matched() -> None:
    """'heyzen' without a space must not trigger the wake phrase."""
    detector = WakeWordDetector(wake_phrase="hey zen")
    found, _ = detector.check_text_for_wake_phrase("heyzen")
    assert found is False


# ---------------------------------------------------------------------------
# wait_for_wake_word
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_wait_for_wake_word_no_microphone_returns_none() -> None:
    """No microphone → None immediately, no STT call made."""
    stt = _MockSTT(response="hey zen")
    detector = WakeWordDetector(wake_phrase="hey zen", stt_engine=stt)

    with patch.object(detector.audio_capture, "is_microphone_available", return_value=False):
        result = await detector.wait_for_wake_word()

    assert result is None


@pytest.mark.asyncio
async def test_wait_for_wake_word_no_stt_engine_returns_none() -> None:
    """stt_engine=None → None immediately."""
    detector = WakeWordDetector(wake_phrase="hey zen", stt_engine=None)
    result = await detector.wait_for_wake_word()
    assert result is None


@pytest.mark.asyncio
async def test_wait_for_wake_word_no_audio_returns_none() -> None:
    """listen_phrase returning None (timeout) → None."""
    stt = _MockSTT(response="hey zen")
    detector = WakeWordDetector(wake_phrase="hey zen", stt_engine=stt)

    with patch.object(detector.audio_capture, "is_microphone_available", return_value=True), \
         patch.object(detector.audio_capture, "listen_phrase", AsyncMock(return_value=None)):
        result = await detector.wait_for_wake_word()

    assert result is None


@pytest.mark.asyncio
async def test_wait_for_wake_word_phrase_detected_emits_event() -> None:
    """Detecting the wake phrase emits WAKE_WORD_DETECTED and returns the command."""
    fake_audio = b"RIFF\x00\x00\x00\x00WAVEfmt "  # minimal non-empty bytes
    stt = _MockSTT(response="hey zen check the time")
    detector = WakeWordDetector(wake_phrase="hey zen", stt_engine=stt)

    emitted_events: list[dict] = []

    async def capture_event(event_type, payload):
        emitted_events.append({"type": event_type, "payload": payload})

    with patch.object(detector.audio_capture, "is_microphone_available", return_value=True), \
         patch.object(detector.audio_capture, "listen_phrase", AsyncMock(return_value=fake_audio)), \
         patch("zen.voice.wake_word.event_bus.emit", side_effect=capture_event):

        result = await detector.wait_for_wake_word()

    assert result is not None
    assert "check the time" in result
    assert len(emitted_events) == 1


@pytest.mark.asyncio
async def test_wait_for_wake_word_no_phrase_in_transcript_returns_none() -> None:
    """Transcription without the wake phrase → None (do not process as a command)."""
    fake_audio = b"RIFF..."
    stt = _MockSTT(response="what is the weather today")
    detector = WakeWordDetector(wake_phrase="hey zen", stt_engine=stt)

    with patch.object(detector.audio_capture, "is_microphone_available", return_value=True), \
         patch.object(detector.audio_capture, "listen_phrase", AsyncMock(return_value=fake_audio)):
        result = await detector.wait_for_wake_word()

    assert result is None
