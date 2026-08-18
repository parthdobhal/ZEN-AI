"""
Abstract Base Class for Speech-to-Text (STT) Engines.
"""

from abc import ABC, abstractmethod
from pathlib import Path


class STTBase(ABC):
    """Abstract interface for speech transcription engines."""

    name: str

    @abstractmethod
    async def transcribe(self, audio_data: bytes) -> str:
        """Transcribe raw audio bytes to text."""
        pass

    @abstractmethod
    async def transcribe_file(self, audio_file_path: Path) -> str:
        """Transcribe an audio file on disk."""
        pass
