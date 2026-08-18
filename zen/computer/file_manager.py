"""
Safe File & Directory Management Tools for Windows.
"""

import os
from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field

from zen.config.constants import RISK_READ_ONLY, ROOT_DIR, WORKSPACE_DIR
from zen.tools.base import BaseTool, ToolResult
from zen.tools.guardrails import validate_path_safety


class SearchFilesParams(BaseModel):
    query: str = Field(description="Filename or glob pattern to search for (e.g. '*.py', 'notes.txt')")
    search_path: str = Field(
        default=str(WORKSPACE_DIR),
        description="Root folder to search within (defaults to workspace)",
    )
    max_results: int = Field(default=20, ge=1, le=50, description="Max matching files to return")


class ListDirParams(BaseModel):
    directory_path: str = Field(
        default=str(WORKSPACE_DIR),
        description="Path to directory to inspect",
    )


class ReadFileParams(BaseModel):
    file_path: str = Field(description="Path to the text file to read")
    max_lines: int = Field(default=150, ge=1, le=500, description="Max lines to read")


class SearchFilesTool(BaseTool):
    """Searches for files matching a pattern within a directory tree."""

    name = "search_files"
    description = "Searches for files and folders by name or glob pattern within a specified directory."
    risk_level = RISK_READ_ONLY
    parameters_schema = SearchFilesParams

    async def execute(self, params: SearchFilesParams, context: Any = None) -> ToolResult:
        try:
            base_dir = validate_path_safety(Path(params.search_path), allow_read_only=True)
            if not base_dir.exists() or not base_dir.is_dir():
                return ToolResult.fail(f"Directory '{base_dir}' does not exist.")

            matches = []
            pattern = params.query if any(c in params.query for c in "*?[]") else f"*{params.query}*"
            
            for root, dirs, files in os.walk(base_dir):
                # Ignore hidden and virtualenv folders to keep laptop fast
                dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("venv", ".venv", "__pycache__", "node_modules")]
                for filename in files:
                    if Path(filename).match(pattern):
                        full_path = Path(root) / filename
                        matches.append(str(full_path))
                        if len(matches) >= params.max_results:
                            break
                if len(matches) >= params.max_results:
                    break

            if not matches:
                return ToolResult.ok(data=[], message=f"No files matching '{params.query}' found in '{base_dir}'.")

            summary = f"Found {len(matches)} matching file(s):\n" + "\n".join(f"- {p}" for p in matches)
            return ToolResult.ok(data=matches, message=summary)
        except Exception as e:
            return ToolResult.fail(f"Search failed: {e}")


class ListDirectoryTool(BaseTool):
    """Lists files and folders inside a directory."""

    name = "list_directory"
    description = "Lists files and subfolders within a specific directory."
    risk_level = RISK_READ_ONLY
    parameters_schema = ListDirParams

    async def execute(self, params: ListDirParams, context: Any = None) -> ToolResult:
        try:
            target_dir = validate_path_safety(Path(params.directory_path), allow_read_only=True)
            if not target_dir.exists():
                return ToolResult.fail(f"Directory '{target_dir}' does not exist.")

            entries = []
            for item in sorted(target_dir.iterdir()):
                if item.name.startswith("."):
                    continue
                type_label = "[DIR]" if item.is_dir() else f"[{round(item.stat().st_size / 1024, 1)} KB]"
                entries.append(f"{type_label} {item.name}")

            summary = f"Contents of '{target_dir}':\n" + "\n".join(entries[:50])
            return ToolResult.ok(data=entries, message=summary)
        except Exception as e:
            return ToolResult.fail(f"Could not list directory: {e}")


class ReadFileTool(BaseTool):
    """Reads content from a text file."""

    name = "read_file"
    description = "Reads text content from a specified file safely."
    risk_level = RISK_READ_ONLY
    parameters_schema = ReadFileParams

    async def execute(self, params: ReadFileParams, context: Any = None) -> ToolResult:
        try:
            target_file = validate_path_safety(Path(params.file_path), allow_read_only=True)
            if not target_file.exists() or not target_file.is_file():
                return ToolResult.fail(f"File '{target_file}' does not exist.")

            # Read first max_lines
            with open(target_file, "r", encoding="utf-8", errors="replace") as f:
                lines = [f.readline() for _ in range(params.max_lines)]
                content = "".join(lines)

            summary = f"Read {len(lines)} lines from {target_file.name}:\n\n{content}"
            return ToolResult.ok(data={"content": content, "lines_read": len(lines)}, message=summary)
        except Exception as e:
            return ToolResult.fail(f"Could not read file: {e}")
