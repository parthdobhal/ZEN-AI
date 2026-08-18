"""
Abstract Base Class and data models for AI Providers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator
from zen.core.session import ChatMessage


@dataclass
class ToolCallRequest:
    """Represents a tool invocation requested by the AI model."""
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class BrainResponse:
    """Final unified response from an AI provider."""
    content: str
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    raw_response: dict[str, Any] = field(default_factory=dict)
    finish_reason: str = "stop"


@dataclass
class BrainDelta:
    """Incremental chunk streamed from an AI provider."""
    content_delta: str = ""
    tool_call_delta: ToolCallRequest | None = None
    is_done: bool = False


class AIProviderBase(ABC):
    """Abstract interface for all swappable LLM backends."""

    name: str

    @abstractmethod
    async def chat_complete(
        self,
        messages: list[ChatMessage],
        system_prompt: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
    ) -> BrainResponse:
        """Execute a complete non-streaming chat completion."""
        pass

    @abstractmethod
    async def stream_chat(
        self,
        messages: list[ChatMessage],
        system_prompt: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
    ) -> AsyncIterator[BrainDelta]:
        """Stream chunks from the model."""
        pass

    @abstractmethod
    async def validate_credentials(self) -> bool:
        """Check whether API keys / server endpoints are reachable and valid."""
        pass
