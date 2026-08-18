"""
Unit tests for Computer Diagnostics and System Tools.
"""

import pytest
from zen.computer.diagnostics import PCDiagnosticsTool
from zen.computer.system_info import SystemInfoTool


@pytest.mark.asyncio
async def test_system_info_tool() -> None:
    tool = SystemInfoTool()
    res = await tool.execute(tool.parameters_schema())
    assert res.success
    assert "cpu_cores" in res.data
    assert "ram_total_gb" in res.data
    assert res.data["cpu_cores"] > 0
    assert "System:" in res.output_message


@pytest.mark.asyncio
async def test_pc_diagnostics_tool() -> None:
    tool = PCDiagnosticsTool()
    res = await tool.execute(tool.parameters_schema(top_process_count=3))
    assert res.success
    assert "health_score" in res.data
    assert 0 <= res.data["health_score"] <= 100
    assert "health_status" in res.data
    assert len(res.data["top_ram_consumers"]) <= 3
