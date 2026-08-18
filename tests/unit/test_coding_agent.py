"""
Unit tests for Autonomous Coding Agent and Self-Debugging.
"""

from pathlib import Path
import pytest
from zen.coding.agent import CodingAgent
from zen.coding.error_analyzer import ErrorAnalyzer
from zen.coding.workspace_manager import WorkspaceManager
from tests.conftest import MockAIProvider


def test_workspace_sandboxing(temp_dir: Path) -> None:
    wm = WorkspaceManager(root_workspace=temp_dir)
    wm.create_project("test_calc")

    # Write file
    file_path = wm.write_file("test_calc", "calculator.py", "def add(a, b):\n    return a + b\n")
    assert file_path.exists()

    # Read back
    content = wm.read_file("test_calc", "calculator.py")
    assert "def add" in content

    # List files
    files = wm.list_project_files("test_calc")
    assert "calculator.py" in files


def test_error_analyzer_traceback_parsing() -> None:
    sample_trace = """
Traceback (most recent call last):
  File "workspace/calculator/tests/test_calc.py", line 8, in test_addition
    assert add(2, 3) == 6
AssertionError: assert 5 == 6
"""
    diag = ErrorAnalyzer.analyze(sample_trace)
    assert diag is not None
    assert diag.exception_type == "AssertionError"
    assert "assert 5 == 6" in diag.message
    assert diag.line_number == 8
    assert "test_calc.py" in diag.failing_file


@pytest.mark.asyncio
async def test_coding_agent_plan_and_scaffold(temp_dir: Path) -> None:
    mock_project_json = """
    {
        "summary": "Simple math module",
        "dependencies": [],
        "files": {
            "math_mod/__init__.py": "",
            "math_mod/core.py": "def multiply(a, b):\\n    return a * b\\n",
            "tests/__init__.py": "",
            "tests/test_core.py": "from math_mod.core import multiply\\nimport unittest\\n\\nclass TestMath(unittest.TestCase):\\n    def test_mul(self):\\n        self.assertEqual(multiply(3, 4), 12)\\n"
        }
    }
    """
    mock_provider = MockAIProvider(response_text=mock_project_json)
    wm = WorkspaceManager(root_workspace=temp_dir)
    agent = CodingAgent(ai_provider=mock_provider, workspace_manager=wm)

    result = await agent.build_project("math_mod", "Create a multiplication module with tests", max_iterations=2)
    assert result["project_name"] == "math_mod"
    assert "math_mod/core.py" in result["files_created"]
    assert "tests/test_core.py" in result["files_created"]
