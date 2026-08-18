"""
VS Code Integration Bridge for Windows.
"""

from pathlib import Path
import subprocess
from pydantic import BaseModel, Field
from zen.config.constants import RISK_SAFE_EXECUTE
from zen.tools.base import BaseTool, ToolResult
from zen.tools.guardrails import validate_path_safety


class VSCodeParams(BaseModel):
    path: str = Field(description="Directory path or file path to open in VS Code")
    line_number: int | None = Field(default=None, description="Optional line number to jump to in the file")


class OpenInVSCodeTool(BaseTool):
    """Launches VS Code pointing to a project directory or opens a specific file at a line."""

    name = "open_in_vscode"
    description = "Opens a project directory or file in Visual Studio Code."
    risk_level = RISK_SAFE_EXECUTE
    parameters_schema = VSCodeParams

    async def execute(self, params: VSCodeParams, context: None = None) -> ToolResult:
        try:
            target = validate_path_safety(Path(params.path), allow_read_only=True)
            if not target.exists():
                return ToolResult.fail(f"Path '{target}' does not exist.")

            cmd = ["code"]
            if params.line_number and target.is_file():
                cmd.extend(["-g", f"{target}:{params.line_number}"])
            else:
                cmd.append(str(target))

            subprocess.Popen(cmd, shell=True)
            return ToolResult.ok(message=f"Opened in VS Code: {target}")
        except Exception as e:
            return ToolResult.fail(f"Failed to open VS Code: {e}")
