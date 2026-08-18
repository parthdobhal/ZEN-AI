"""
Session and conversation state manager for active interactions.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """Represents a single message in a conversation."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None
    name: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class SessionContext:
    """Active conversational and execution session state."""
    session_id: str = field(default_factory=lambda: str(uuid4()))
    active_project_path: str | None = None
    messages: list[ChatMessage] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    is_voice_mode: bool = False
    turn_count: int = 0

    def add_user_message(self, content: str) -> ChatMessage:
        msg = ChatMessage(role="user", content=content)
        self.messages.append(msg)
        self.turn_count += 1
        return msg

    def add_assistant_message(
        self,
        content: str,
        tool_calls: list[dict[str, Any]] | None = None,
    ) -> ChatMessage:
        msg = ChatMessage(role="assistant", content=content, tool_calls=tool_calls)
        self.messages.append(msg)
        return msg

    def add_tool_message(self, tool_call_id: str, name: str, content: str) -> ChatMessage:
        msg = ChatMessage(role="tool", tool_call_id=tool_call_id, name=name, content=content)
        self.messages.append(msg)
        return msg

    def get_recent_messages(self, limit: int = 20) -> list[ChatMessage]:
        """Retrieve recent conversation history for prompt construction."""
        return self.messages[-limit:]
