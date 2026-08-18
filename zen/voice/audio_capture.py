"""
Audio Capture and Microphone Stream Manager using SoundDevice.
"""

import asyncio
import io
import math
import struct
import time
import wave
import sounddevice as sd

from zen.core.logger import logger


class AudioCapture:
    """Non-blocking audio capture interface for Windows using sounddevice."""

    def __init__(
        self,
        sample_rate: int = 16000,
        chunk_duration_ms: int = 100,
        energy_threshold: float = 350.0,
        pause_threshold: float = 0.8,
    ) -> None:
        self.sample_rate = sample_rate
        self.chunk_duration_ms = chunk_duration_ms
        self.chunk_samples = int(self.sample_rate * (self.chunk_duration_ms / 1000.0))
        self.chunk_bytes = self.chunk_samples * 2  # 16-bit PCM = 2 bytes per sample
        self.energy_threshold = energy_threshold
        self.dynamic_energy_threshold = True
        self.pause_threshold = pause_threshold

    def is_microphone_available(self) -> bool:
        """Check if any recording input device is connected."""
        try:
            devices = sd.query_devices()
            if isinstance(devices, dict):
                devices = [devices]
            return any(d.get("max_input_channels", 0) > 0 for d in devices)
        except Exception as e:
            logger.debug(f"Microphone availability check failed: {e}")
            return False

    def _calculate_rms(self, pcm_bytes: bytes) -> float:
        """Calculate Root Mean Square (RMS) energy of 16-bit PCM audio."""
        count = len(pcm_bytes) // 2
        if count == 0:
            return 0.0
        try:
            samples = struct.unpack(f"<{count}h", pcm_bytes[: count * 2])
            sum_squares = sum(s * s for s in samples)
            return math.sqrt(sum_squares / count)
        except Exception:
            return 0.0

    def _pcm_to_wav(self, pcm_data: bytes) -> bytes:
        """Encodes raw 16-bit Mono PCM bytes to standard WAV bytes."""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(pcm_data)
        return buf.getvalue()

    async def listen_phrase(
        self,
        timeout: float = 8.0,
        phrase_time_limit: float = 12.0,
    ) -> bytes | None:
        """
        Listens on the default microphone for a single spoken phrase
        and returns the WAV audio bytes, or None on timeout/silence.
        """
        def _record_sync() -> bytes | None:
            if not self.is_microphone_available():
                logger.debug("No recording device available.")
                return None

            try:
                with sd.RawInputStream(
                    samplerate=self.sample_rate,
                    channels=1,
                    dtype="int16",
                    blocksize=self.chunk_samples,
                ) as stream:
                    # 1. Ambient noise calibration (0.3s)
                    ambient_energies: list[float] = []
                    if self.dynamic_energy_threshold:
                        for _ in range(3):
                            data, _ = stream.read(self.chunk_samples)
                            if data:
                                ambient_energies.append(self._calculate_rms(data))
                        if ambient_energies:
                            ambient_avg = sum(ambient_energies) / len(ambient_energies)
                            # Set threshold safely above ambient floor
                            self.energy_threshold = max(350.0, ambient_avg * 1.5)

                    # 2. Listen for speech onset with rolling pre-speech buffer
                    pre_buffer: list[bytes] = []
                    max_pre_buffer_chunks = 4  # keep ~400ms prior context
                    start_time = time.monotonic()
                    speech_started = False

                    while not speech_started:
                        if time.monotonic() - start_time > timeout:
                            return None

                        data, _ = stream.read(self.chunk_samples)
                        if not data:
                            continue

                        pre_buffer.append(data)
                        if len(pre_buffer) > max_pre_buffer_chunks:
                            pre_buffer.pop(0)

                        rms = self._calculate_rms(data)
                        if rms >= self.energy_threshold:
                            speech_started = True
                            break

                    # 3. Record phrase until pause_threshold or phrase_time_limit
                    recorded_chunks: list[bytes] = list(pre_buffer)
                    phrase_start_time = time.monotonic()
                    silence_start_time: float | None = None

                    while True:
                        elapsed_phrase = time.monotonic() - phrase_start_time
                        if elapsed_phrase >= phrase_time_limit:
                            break

                        data, _ = stream.read(self.chunk_samples)
                        if not data:
                            continue

                        recorded_chunks.append(data)
                        rms = self._calculate_rms(data)

                        if rms < self.energy_threshold:
                            if silence_start_time is None:
                                silence_start_time = time.monotonic()
                            elif time.monotonic() - silence_start_time >= self.pause_threshold:
                                # Silence threshold exceeded; phrase complete
                                break
                        else:
                            silence_start_time = None

                    pcm_data = b"".join(recorded_chunks)
                    if not pcm_data:
                        return None

                    return self._pcm_to_wav(pcm_data)

            except Exception as e:
                logger.debug(f"Audio capture error: {e}")
                return None

        return await asyncio.to_thread(_record_sync)
