"""
Local Windows SAPI5 / pyttsx3 TTS Fallback Engine.

pyttsx3 is lazy-imported inside ``__init__`` to avoid a hard dependency on a
package whose Python 3.14 compatibility on Windows is not yet confirmed.
If pyttsx3 is unavailable, ``SAPITTSEngine()`` raises ``ImportError`` with an
actionable message so ``VoiceManager`` can fall through to ``EdgeTTSEngine``.
"""

import asyncio
from pathlib import Path
from zen.core.events import EventType, event_bus
from zen.core.logger import logger
from zen.voice.tts_base import TTSBase


class SAPITTSEngine(TTSBase):
    """
    Offline text-to-speech fallback using native Windows SAPI5 via pyttsx3.

    Raises:
        ImportError: If pyttsx3 is not installed or not compatible with the
            running Python version.  Use ``ZEN_VOICE_ENGINE=edge_tts`` in your
            ``.env`` to avoid this engine entirely.
    """

    name = "sapi"

    def __init__(self, rate: int = 190) -> None:
        try:
            import pyttsx3 as _pyttsx3  # noqa: PLC0415  (lazy import by design)
            self._pyttsx3 = _pyttsx3
        except ImportError as exc:
            raise ImportError(
                "pyttsx3 is not available on this Python version. "
                "Use EdgeTTSEngine instead by setting ZEN_VOICE_ENGINE=edge_tts in your .env file."
            ) from exc
        self.rate = rate
        self._is_speaking = False

    async def speak(self, text: str) -> None:
        if not text.strip():
            return

        await event_bus.emit(EventType.SPEECH_START, {"text": text})
        self._is_speaking = True

        def _run_sapi() -> None:
            try:
                engine = self._pyttsx3.init()
                engine.setProperty("rate", self.rate)
                engine.say(text)
                engine.runAndWait()
            except Exception as e:
                logger.debug(f"SAPI error: {e}")

        try:
            await asyncio.to_thread(_run_sapi)
        finally:
            self._is_speaking = False
            await event_bus.emit(EventType.SPEECH_END, {"text": text})

    async def save_to_file(self, text: str, output_path: Path) -> Path:
        def _save() -> None:
            engine = self._pyttsx3.init()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            engine.save_to_file(text, str(output_path))
            engine.runAndWait()

        await asyncio.to_thread(_save)
        return output_path

    def stop(self) -> None:
        self._is_speaking = False
