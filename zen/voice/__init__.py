"""
ZEN Voice Subsystem
"""

from zen.voice.tts_base import TTSBase
from zen.voice.stt_base import STTBase
from zen.voice.tts.edge_tts_engine import EdgeTTSEngine
from zen.voice.tts.sapi_engine import SAPITTSEngine
from zen.voice.stt.groq_whisper import GroqWhisperSTT, SpeechRecognitionSTT, STTUnavailableError
from zen.voice.audio_capture import AudioCapture
from zen.voice.wake_word import WakeWordDetector
from zen.voice.voice_manager import VoiceManager
from zen.voice.text_utils import strip_markdown_for_tts

__all__ = [
    "TTSBase",
    "STTBase",
    "EdgeTTSEngine",
    "SAPITTSEngine",
    "GroqWhisperSTT",
    "SpeechRecognitionSTT",
    "STTUnavailableError",
    "AudioCapture",
    "WakeWordDetector",
    "VoiceManager",
    "strip_markdown_for_tts",
]
