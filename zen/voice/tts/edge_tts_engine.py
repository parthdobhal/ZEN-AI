"""
Neural Text-to-Speech Engine using Edge-TTS.
"""

import asyncio
import os
from pathlib import Path
import subprocess
import tempfile
import edge_tts

from zen.config.constants import CACHE_DIR
from zen.core.events import EventType, event_bus
from zen.core.logger import logger
from zen.voice.tts_base import TTSBase


class EdgeTTSEngine(TTSBase):
    """Microsoft Neural TTS provider via pure-Python async edge-tts."""

    name = "edge_tts"

    def __init__(
        self,
        voice: str = "en-US-GuyNeural",
        rate: str = "+0%",
        pitch: str = "+0Hz",
    ) -> None:
        self.voice = voice
        self.rate = rate
        self.pitch = pitch
        self._current_process: subprocess.Popen | None = None

    async def save_to_file(self, text: str, output_path: Path) -> Path:
        """Synthesize text and save to MP3 file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        communicate = edge_tts.Communicate(text, self.voice, rate=self.rate, pitch=self.pitch)
        await communicate.save(str(output_path))
        return output_path

    async def speak(self, text: str) -> None:
        """Synthesize text and play aloud on Windows."""
        if not text.strip():
            return

        await event_bus.emit(EventType.SPEECH_START, {"text": text})
        temp_file = Path(tempfile.gettempdir()) / f"zen_tts_{os.getpid()}.mp3"

        try:
            await self.save_to_file(text, temp_file)

            # Play audio file on Windows using PowerShell / Media Player
            play_script = (
                f"$player = New-Object System.Media.SoundPlayer; "
                f"$wmp = New-Object -ComObject WMPlayer.OCX; "
                f"$wmp.URL = '{str(temp_file).replace(chr(92), chr(92)+chr(92))}'; "
                f"$wmp.controls.play(); "
                f"while ($wmp.playState -ne 1) {{ Start-Sleep -Milliseconds 100 }}; "
                f"$wmp.close()"
            )

            # Start playback
            self._current_process = subprocess.Popen(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", play_script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            # Await completion asynchronously without blocking event loop
            while self._current_process and self._current_process.poll() is None:
                await asyncio.sleep(0.05)

        except Exception as e:
            logger.debug(f"EdgeTTS playback error: {e}")
        finally:
            self._current_process = None
            try:
                if temp_file.exists():
                    temp_file.unlink(missing_ok=True)
            except Exception:
                pass
            await event_bus.emit(EventType.SPEECH_END, {"text": text})

    def stop(self) -> None:
        """Interrupt and terminate ongoing audio playback immediately."""
        if self._current_process and self._current_process.poll() is None:
            try:
                self._current_process.terminate()
                self._current_process.kill()
                logger.debug("TTS playback interrupted.")
            except Exception as e:
                logger.debug(f"Failed to kill TTS process: {e}")
            finally:
                self._current_process = None
