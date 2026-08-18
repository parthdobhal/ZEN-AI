"""
Integration tests for ZenOrchestrator full request pipeline.
"""

from pathlib import Path
import pytest
from zen.brain.provider_base import ToolCallRequest
from zen.config.settings import Settings
from zen.core.orchestrator import ZenOrchestrator
from zen.core.session import SessionContext
from tests.conftest import MockAIProvider


@pytest.mark.asyncio
async def test_orchestrator_direct_message(temp_dir: Path) -> None:
    settings = Settings(
        ZEN_WORKSPACE_DIR=temp_dir / "workspace",
        ZEN_DATA_DIR=temp_dir / "data",
        ZEN_VOICE_ENABLED=False,
    )
    orchestrator = ZenOrchestrator(settings)
    orchestrator.provider = MockAIProvider(response_text="I can assist you with your PC tasks.")

    session = SessionContext()
    response = await orchestrator.process_user_message("What can you do?", session=session)

    assert response == "I can assist you with your PC tasks."
    assert len(session.messages) == 2
    assert session.messages[0].role == "user"
    assert session.messages[1].role == "assistant"


@pytest.mark.asyncio
async def test_orchestrator_tool_invocation_flow(temp_dir: Path) -> None:
    settings = Settings(
        ZEN_WORKSPACE_DIR=temp_dir / "workspace",
        ZEN_DATA_DIR=temp_dir / "data",
        ZEN_VOICE_ENABLED=False,
    )
    orchestrator = ZenOrchestrator(settings)
    
    # Mock a tool call requesting get_system_info
    tool_call = ToolCallRequest(
        id="call_sys_info",
        name="get_system_info",
        arguments={"include_disks": True, "include_network": False},
    )
    orchestrator.provider = MockAIProvider(
        response_text="Your PC is running at low CPU usage and has plenty of RAM.",
        tool_calls=[tool_call],
    )

    session = SessionContext()
    response = await orchestrator.process_user_message("How is my system doing?", session=session)

    assert "plenty of RAM" in response
    # Verify tool message was recorded in session
    tool_messages = [m for m in session.messages if m.role == "tool"]
    assert len(tool_messages) == 1
    assert tool_messages[0].name == "get_system_info"
    assert "System:" in tool_messages[0].content
