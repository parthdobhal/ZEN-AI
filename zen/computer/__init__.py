"""
ZEN Computer & Windows Control Subsystem
"""

from zen.computer.system_info import SystemInfoTool
from zen.computer.diagnostics import PCDiagnosticsTool
from zen.computer.app_launcher import LaunchAppTool, OpenUrlTool
from zen.computer.file_manager import SearchFilesTool, ListDirectoryTool, ReadFileTool
from zen.computer.vscode_bridge import OpenInVSCodeTool
from zen.tools.registry import ToolRegistry


def register_computer_tools(registry: ToolRegistry) -> None:
    """Register all computer control and diagnostic tools with the tool registry."""
    registry.register(SystemInfoTool())
    registry.register(PCDiagnosticsTool())
    registry.register(LaunchAppTool())
    registry.register(OpenUrlTool())
    registry.register(SearchFilesTool())
    registry.register(ListDirectoryTool())
    registry.register(ReadFileTool())
    registry.register(OpenInVSCodeTool())


__all__ = [
    "SystemInfoTool",
    "PCDiagnosticsTool",
    "LaunchAppTool",
    "OpenUrlTool",
    "SearchFilesTool",
    "ListDirectoryTool",
    "ReadFileTool",
    "OpenInVSCodeTool",
    "register_computer_tools",
]
