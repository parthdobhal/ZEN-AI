"""
Unit tests for AudioCapture (SoundDevice + Wave).
"""

import io
import struct
import sys
import wave
from unittest.mock import MagicMock, patch
import pytest

from zen.voice.audio_capture import AudioCapture


def test_audio_capture_initialization() -> None:
    capture = AudioCapture(sample_rate=16000, chunk_duration_ms=100)
    assert capture.sample_rate == 16000
    assert capture.chunk_samples == 1600
    assert capture.chunk_bytes == 3200
    assert capture.energy_threshold == 350.0
    assert capture.pause_threshold == 0.8


def test_calculate_rms_silence_and_signal() -> None:
    capture = AudioCapture()
    # Empty
    assert capture._calculate_rms(b"") == 0.0

    # Silence (all zeros)
    silence = b"\x00\x00" * 100
    assert capture._calculate_rms(silence) == 0.0

    # Constant signal
    val = 1000
    signal = struct.pack("<100h", *([val] * 100))
    assert pytest.approx(capture._calculate_rms(signal), 0.1) == float(val)


def test_pcm_to_wav_encoding() -> None:
    capture = AudioCapture(sample_rate=16000)
    pcm_data = struct.pack("<1600h", *([500] * 1600))  # 1600 samples
    wav_bytes = capture._pcm_to_wav(pcm_data)

    assert wav_bytes.startswith(b"RIFF")
    # Verify WAV header
    buf = io.BytesIO(wav_bytes)
    with wave.open(buf, "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 16000
        assert wf.getnframes() == 1600


def test_is_microphone_available_mock() -> None:
    capture = AudioCapture()

    # Case A: Devices present with input channels
    with patch("sounddevice.query_devices", return_value=[{"name": "Mic", "max_input_channels": 2}]):
        assert capture.is_microphone_available() is True

    # Case B: Devices present with 0 input channels
    with patch("sounddevice.query_devices", return_value=[{"name": "Speaker", "max_input_channels": 0}]):
        assert capture.is_microphone_available() is False

    # Case C: Exception raised
    with patch("sounddevice.query_devices", side_effect=Exception("Driver error")):
        assert capture.is_microphone_available() is False


@pytest.mark.asyncio
async def test_listen_phrase_no_mic() -> None:
    capture = AudioCapture()
    with patch.object(capture, "is_microphone_available", return_value=False):
        result = await capture.listen_phrase(timeout=0.1)
        assert result is None


@pytest.mark.asyncio
async def test_listen_phrase_speech_detection() -> None:
    capture = AudioCapture(sample_rate=16000, chunk_duration_ms=100)

    # 100ms of speech PCM (RMS > 350)
    speech_chunk = struct.pack("<1600h", *([2000] * 1600))
    # 100ms of silence PCM (RMS = 0)
    silence_chunk = b"\x00\x00" * 1600

    # Stream returns:
    # 3 calibration chunks, then 1 speech chunk, then 9 silence chunks (to exceed 0.8s pause_threshold)
    stream_chunks = [silence_chunk] * 3 + [speech_chunk] + [silence_chunk] * 10
    stream_iter = iter(stream_chunks)

    mock_stream = MagicMock()
    mock_stream.read.side_effect = lambda samples: (next(stream_iter, silence_chunk), False)
    mock_stream.__enter__.return_value = mock_stream
    mock_stream.__exit__.return_value = None

    with patch.object(capture, "is_microphone_available", return_value=True), \
         patch("sounddevice.RawInputStream", return_value=mock_stream):
        
        result = await capture.listen_phrase(timeout=1.0, phrase_time_limit=3.0)
        assert result is not None
        assert result.startswith(b"RIFF")

        # Verify decoded frames
        buf = io.BytesIO(result)
        with wave.open(buf, "rb") as wf:
            assert wf.getframerate() == 16000
            assert wf.getnchannels() == 1
            assert wf.getnframes() > 0


def test_no_pyaudio_import_in_audio_capture() -> None:
    """
    Importing zen.voice.audio_capture must NOT cause pyaudio to be loaded.

    This is a regression guard: AudioCapture uses sounddevice exclusively.
    If pyaudio ever appears in sys.modules after this import, a dependency has
    been introduced that violates the Python 3.14 compatibility requirement.
    """
    pyaudio_keys = [k for k in sys.modules if "pyaudio" in k.lower()]
    assert pyaudio_keys == [], (
        f"pyaudio was unexpectedly imported by zen.voice.audio_capture: {pyaudio_keys}"
    )
