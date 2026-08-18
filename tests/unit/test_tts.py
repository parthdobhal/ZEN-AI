"""
Unit tests for Text-to-Speech (TTS) engines and the Markdown stripping utility.
"""

import sys
import asyncio
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
import pytest

from zen.voice.tts_base import TTSBase
from zen.voice.text_utils import strip_markdown_for_tts


# ---------------------------------------------------------------------------
# TTSBase
# ---------------------------------------------------------------------------

def test_tts_base_is_abstract() -> None:
    """TTSBase cannot be instantiated directly."""
    with pytest.raises(TypeError):
        TTSBase()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# strip_markdown_for_tts
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw, expected_not_in", [
    ("**bold text**", "**"),
    ("*italic text*", "*"),
    ("`inline code`", "`"),
    ("# Heading One", "#"),
    ("## Heading Two", "#"),
    ("[link text](https://example.com)", "https://example.com"),
    ("![alt text](image.png)", "image.png"),
    ("> blockquote line", ">"),
    ("---", "---"),
    ("- bullet item", "-"),
    ("1. numbered item", "1."),
])
def test_strip_markdown_removes_formatting(raw: str, expected_not_in: str) -> None:
    result = strip_markdown_for_tts(raw)
    assert expected_not_in not in result, (
        f"Expected '{expected_not_in}' to be stripped from: {raw!r}\nGot: {result!r}"
    )


def test_strip_markdown_preserves_plain_text() -> None:
    plain = "Hello, this is a normal sentence."
    assert strip_markdown_for_tts(plain) == plain


def test_strip_markdown_preserves_link_display_text() -> None:
    md = "Visit [ZEN documentation](https://example.com) for more info."
    result = strip_markdown_for_tts(md)
    assert "ZEN documentation" in result
    assert "https://example.com" not in result


def test_strip_markdown_fenced_code_block_replaced() -> None:
    md = "Here is some code:\n```python\nprint('hello')\n```\nEnd."
    result = strip_markdown_for_tts(md)
    assert "```" not in result
    assert "print" not in result
    # Should be replaced with a spoken label
    assert "[code block]" in result


def test_strip_markdown_empty_string() -> None:
    assert strip_markdown_for_tts("") == ""


def test_strip_markdown_none_safe() -> None:
    # Should handle falsy-but-valid input gracefully
    result = strip_markdown_for_tts("  ")
    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# SAPITTSEngine — lazy import guard
# ---------------------------------------------------------------------------

def test_sapi_engine_raises_import_error_when_pyttsx3_absent() -> None:
    """
    SAPITTSEngine() must raise ImportError with an actionable message
    when pyttsx3 is not importable.
    """
    with patch.dict(sys.modules, {"pyttsx3": None}):
        # Force reimport so the lazy import path is exercised
        from zen.voice.tts.sapi_engine import SAPITTSEngine
        with pytest.raises(ImportError) as exc_info:
            SAPITTSEngine()

    msg = str(exc_info.value)
    assert "pyttsx3" in msg
    # Should suggest the EdgeTTS alternative
    assert "edge_tts" in msg.lower() or "EdgeTTSEngine" in msg


def test_sapi_engine_import_error_message_contains_env_guidance() -> None:
    """The ImportError from missing pyttsx3 must mention the .env setting."""
    with patch.dict(sys.modules, {"pyttsx3": None}):
        from zen.voice.tts.sapi_engine import SAPITTSEngine
        with pytest.raises(ImportError) as exc_info:
            SAPITTSEngine()
    assert "ZEN_VOICE_ENGINE" in str(exc_info.value) or "edge_tts" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# EdgeTTSEngine — speak and stop
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_edge_tts_speak_empty_text_is_noop() -> None:
    """EdgeTTSEngine.speak() must return immediately for blank input."""
    from zen.voice.tts.edge_tts_engine import EdgeTTSEngine

    engine = EdgeTTSEngine()
    # No mock needed — blank text should short-circuit before any I/O
    await engine.speak("   ")  # Should not raise


@pytest.mark.asyncio
async def test_edge_tts_stop_with_no_active_process() -> None:
    """EdgeTTSEngine.stop() is a no-op when nothing is playing."""
    from zen.voice.tts.edge_tts_engine import EdgeTTSEngine

    engine = EdgeTTSEngine()
    engine.stop()  # Should not raise


@pytest.mark.asyncio
async def test_edge_tts_stop_kills_process() -> None:
    """EdgeTTSEngine.stop() terminates the subprocess if one is running."""
    from zen.voice.tts.edge_tts_engine import EdgeTTSEngine

    engine = EdgeTTSEngine()
    mock_proc = MagicMock(spec=subprocess.Popen)
    mock_proc.poll.return_value = None  # Still running
    engine._current_process = mock_proc

    engine.stop()

    mock_proc.terminate.assert_called_once()
    mock_proc.kill.assert_called_once()
    assert engine._current_process is None
