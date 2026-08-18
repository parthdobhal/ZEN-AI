"""
Abstract Base Class for Text-to-Speech (TTS) Engines.
"""

from abc import ABC, abstractmethod
from pathlib import Path


class TTSBase(ABC):
    """Abstract interface for all Text-to-Speech backends."""

    name: str

    @abstractmethod
    async def speak(self, text: str) -> None:
        """Synthesizes text and plays audio aloud."""
        pass

    @abstractmethod
    async def save_to_file(self, text: str, output_path: Path) -> Path:
        """Synthesizes speech and writes to an audio file."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Interrupts and stops ongoing speech playback."""
        pass
