"""
ZEN Autonomous Coding Subsystem
"""

from zen.coding.workspace_manager import WorkspaceManager
from zen.coding.environment import ProjectEnvironment
from zen.coding.test_runner import TestRunner, TestResult
from zen.coding.error_analyzer import ErrorAnalyzer, DiagnosticError
from zen.coding.agent import CodingAgent, CreateCodingProjectTool, RunProjectTestsTool
from zen.tools.registry import ToolRegistry


def register_coding_tools(registry: ToolRegistry, coding_agent: CodingAgent) -> None:
    """Register coding tools with the tool registry."""
    registry.register(CreateCodingProjectTool(coding_agent))
    registry.register(RunProjectTestsTool(coding_agent.workspace))


__all__ = [
    "WorkspaceManager",
    "ProjectEnvironment",
    "TestRunner",
    "TestResult",
    "ErrorAnalyzer",
    "DiagnosticError",
    "CodingAgent",
    "CreateCodingProjectTool",
    "RunProjectTestsTool",
    "register_coding_tools",
]
