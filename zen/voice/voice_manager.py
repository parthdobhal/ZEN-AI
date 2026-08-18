"""
Voice Subsystem Coordinator for ZEN.

Responsibilities:
- Selects TTS engine at startup (EdgeTTS primary; SAPI optional fallback).
- Selects STT engine at startup (GroqWhisper if key is present).
- Exposes ``speak()``, ``listen_and_transcribe()``, and the ``wake_detector``.
- Strips Markdown from text before passing it to TTS so responses sound natural.
- Raises ``STTUnavailableError`` with an actionable message when no STT backend
  is configured, rather than hanging or silently returning empty strings.
"""

from zen.config.settings import Settings, get_settings
from zen.core.logger import logger
from zen.voice.audio_capture import AudioCapture
from zen.voice.stt.groq_whisper import GroqWhisperSTT, STTUnavailableError
from zen.voice.stt_base import STTBase
from zen.voice.text_utils import strip_markdown_for_tts
from zen.voice.tts.edge_tts_engine import EdgeTTSEngine
from zen.voice.tts_base import TTSBase
from zen.voice.wake_word import WakeWordDetector


def _build_tts(settings: Settings) -> TTSBase:
    """Instantiate the configured TTS engine with automatic SAPI → EdgeTTS fallback."""
    if settings.voice_engine == "sapi":
        try:
            from zen.voice.tts.sapi_engine import SAPITTSEngine  # noqa: PLC0415
            engine = SAPITTSEngine()
            logger.debug("TTS engine: SAPI (pyttsx3)")
            return engine
        except ImportError as exc:
            logger.warning(
                f"SAPITTSEngine unavailable ({exc}). "
                "Falling back to EdgeTTSEngine automatically."
            )

    # Default / fallback: EdgeTTS
    engine = EdgeTTSEngine(
        voice=settings.voice_name,
        rate=settings.voice_speed,
    )
    logger.debug("TTS engine: EdgeTTS")
    return engine


def _build_stt(settings: Settings) -> STTBase | None:
    """
    Instantiate the STT engine.

    Returns ``None`` when no key is available so callers can decide whether
    to surface a helpful error or silently skip STT (e.g., in TTS-only mode).
    """
    if settings.groq_api_key:
        logger.debug("STT engine: Groq Whisper")
        return GroqWhisperSTT(api_key=settings.groq_api_key)

    # No key configured — log once at startup so the user knows.
    logger.warning(
        "No GROQ_API_KEY found. Voice input (STT) is unavailable. "
        "Set GROQ_API_KEY in your .env file to enable speech recognition."
    )
    return None


class VoiceManager:
    """Manages speech synthesis, audio capture, and speech recognition."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.audio_capture = AudioCapture()

        self.tts: TTSBase = _build_tts(self.settings)
        self._stt: STTBase | None = _build_stt(self.settings)

        # Wake word detector — stt may be None; WakeWordDetector handles that case.
        self.wake_detector = WakeWordDetector(
            wake_phrase=self.settings.wake_phrase,
            stt_engine=self._stt,
            audio_capture=self.audio_capture,
        )

    async def speak(self, text: str) -> None:
        """
        Speak the response aloud if voice output is enabled.

        Markdown formatting is stripped before synthesis so that symbols like
        ``**bold**`` or `` ``` `` are not read literally by the TTS engine.
        """
        if not self.settings.voice_enabled or not text.strip():
            return
        plain_text = strip_markdown_for_tts(text)
        if plain_text.strip():
            await self.tts.speak(plain_text)

    def stop_speaking(self) -> None:
        """Interrupt any currently playing speech."""
        self.tts.stop()

    async def listen_and_transcribe(self, timeout: float = 8.0) -> str:
        """
        Capture microphone audio and transcribe it to a text string.

        Raises:
            STTUnavailableError: If no STT backend is configured. The error
                message contains actionable guidance for the user.
        """
        if self._stt is None:
            raise STTUnavailableError(STTUnavailableError.DEFAULT_MESSAGE)

        audio_data = await self.audio_capture.listen_phrase(timeout=timeout)
        if not audio_data:
            return ""
        return await self._stt.transcribe(audio_data)
