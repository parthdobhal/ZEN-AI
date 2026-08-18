"""
Lightweight Wake-Word Detection Engine.
"""

import re
from zen.core.events import EventType, event_bus
from zen.core.logger import logger
from zen.voice.audio_capture import AudioCapture
from zen.voice.stt_base import STTBase


class WakeWordDetector:
    """Detects wake phrase (e.g., 'hey zen') from audio stream."""

    def __init__(
        self,
        wake_phrase: str = "hey zen",
        stt_engine: STTBase | None = None,
        audio_capture: AudioCapture | None = None,
    ) -> None:
        self.wake_phrase = wake_phrase.lower().strip()
        self.stt_engine = stt_engine
        self.audio_capture = audio_capture or AudioCapture()
        self._pattern = re.compile(rf"\b{re.escape(self.wake_phrase)}\b", re.IGNORECASE)

    def check_text_for_wake_phrase(self, text: str) -> tuple[bool, str]:
        """
        Check if text contains the wake phrase.
        Returns (is_present, remainder_command_text).
        """
        match = self._pattern.search(text)
        if match:
            start, end = match.span()
            remainder = (text[:start] + " " + text[end:]).strip()
            return True, remainder
        return False, text

    async def wait_for_wake_word(self) -> str | None:
        """
        Listens until wake phrase is spoken.
        Returns the command trailing the wake phrase, or empty string if just wake phrase.
        """
        if not self.audio_capture.is_microphone_available():
            logger.debug("No microphone available for wake word detection.")
            return None

        if not self.stt_engine:
            return None

        audio_bytes = await self.audio_capture.listen_phrase(timeout=5.0, phrase_time_limit=4.0)
        if not audio_bytes:
            return None

        transcription = await self.stt_engine.transcribe(audio_bytes)
        if not transcription:
            return None

        has_wake, command = self.check_text_for_wake_phrase(transcription)
        if has_wake:
            await event_bus.emit(EventType.WAKE_WORD_DETECTED, {"transcription": transcription, "command": command})
            return command

        return None
