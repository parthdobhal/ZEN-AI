"""
Unit tests for Tool Permission Engine & Risk Verification.
"""

import pytest
from pydantic import BaseModel
from zen.config.constants import RISK_CONFIRM_NEEDED, RISK_READ_ONLY, RISK_RESTRICTED, RISK_SAFE_EXECUTE
from zen.tools.base import BaseTool, ToolResult
from zen.tools.permissions import PermissionDeniedError, PermissionEngine
from zen.tools.registry import ToolRegistry


class DummyParams(BaseModel):
    value: str = "test"


class ReadOnlyTool(BaseTool):
    name = "test_read"
    description = "Read tool"
    risk_level = RISK_READ_ONLY
    parameters_schema = DummyParams

    async def execute(self, params: DummyParams, context: None = None) -> ToolResult:
        return ToolResult.ok(f"Read: {params.value}")


class SensitiveTool(BaseTool):
    name = "test_sensitive"
    description = "Sensitive operation"
    risk_level = RISK_CONFIRM_NEEDED
    parameters_schema = DummyParams

    async def execute(self, params: DummyParams, context: None = None) -> ToolResult:
        return ToolResult.ok(f"Executed: {params.value}")


class RestrictedTool(BaseTool):
    name = "test_restricted"
    description = "Forbidden operation"
    risk_level = RISK_RESTRICTED
    parameters_schema = DummyParams

    async def execute(self, params: DummyParams, context: None = None) -> ToolResult:
        return ToolResult.ok("Should never run")


@pytest.mark.asyncio
async def test_read_only_tool_auto_executes(permission_engine: PermissionEngine) -> None:
    registry = ToolRegistry(permission_engine=permission_engine)
    registry.register(ReadOnlyTool())

    res = await registry.execute("test_read", {"value": "hello"})
    assert res.success
    assert res.data == "Read: hello"


@pytest.mark.asyncio
async def test_restricted_tool_is_blocked(permission_engine: PermissionEngine) -> None:
    registry = ToolRegistry(permission_engine=permission_engine)
    registry.register(RestrictedTool())

    res = await registry.execute("test_restricted", {})
    assert not res.success
    assert "RESTRICTED" in res.error


@pytest.mark.asyncio
async def test_sensitive_tool_user_confirmation(permission_engine: PermissionEngine) -> None:
    registry = ToolRegistry(permission_engine=permission_engine)
    registry.register(SensitiveTool())

    # Case A: User grants confirmation
    async def confirm_yes(name: str, prompt: str, params: dict) -> bool:
        return True

    res_granted = await registry.execute("test_sensitive", {"value": "secure_task"}, confirm_callback=confirm_yes)
    assert res_granted.success
    assert res_granted.data == "Executed: secure_task"

    # Case B: User denies confirmation
    async def confirm_no(name: str, prompt: str, params: dict) -> bool:
        return False

    res_denied = await registry.execute("test_sensitive", {"value": "secure_task"}, confirm_callback=confirm_no)
    assert not res_denied.success
    assert "denied permission" in res_denied.error.lower()
