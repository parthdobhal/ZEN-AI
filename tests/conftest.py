"""
Pytest configuration, mock fixtures, and temporary test databases.
"""

from pathlib import Path
import tempfile
from typing import Any, AsyncIterator
import pytest

from zen.brain.provider_base import AIProviderBase, BrainDelta, BrainResponse, ToolCallRequest
from zen.config.settings import Settings
from zen.core.session import ChatMessage
from zen.memory.memory_manager import MemoryManager
from zen.tools.permissions import PermissionEngine
from zen.tools.registry import ToolRegistry


class MockAIProvider(AIProviderBase):
    """Mock AI Provider for deterministic unit & integration tests."""

    name = "mock_provider"

    def __init__(self, response_text: str = "Hello! I am ZEN.", tool_calls: list[ToolCallRequest] | None = None) -> None:
        self.response_text = response_text
        self.mock_tool_calls = tool_calls or []
        self.call_history: list[list[ChatMessage]] = []

    async def validate_credentials(self) -> bool:
        return True

    async def chat_complete(
        self,
        messages: list[ChatMessage],
        system_prompt: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
    ) -> BrainResponse:
        self.call_history.append(messages)
        # If we have mock tool calls and haven't answered tool results yet:
        if self.mock_tool_calls and not any(m.role == "tool" for m in messages):
            return BrainResponse(content="", tool_calls=self.mock_tool_calls)
        return BrainResponse(content=self.response_text)

    async def stream_chat(
        self,
        messages: list[ChatMessage],
        system_prompt: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
    ) -> AsyncIterator[BrainDelta]:
        yield BrainDelta(content_delta=self.response_text)
        yield BrainDelta(is_done=True)


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def memory_manager(temp_dir: Path) -> MemoryManager:
    db_path = temp_dir / "test_memory.db"
    return MemoryManager(db_path)


@pytest.fixture
def permission_engine(temp_dir: Path, memory_manager: MemoryManager) -> PermissionEngine:
    audit_log = temp_dir / "audit.log"
    return PermissionEngine(memory_manager=memory_manager, audit_log_path=audit_log, require_confirmation=True)


@pytest.fixture
def tool_registry(permission_engine: PermissionEngine) -> ToolRegistry:
    return ToolRegistry(permission_engine=permission_engine)
