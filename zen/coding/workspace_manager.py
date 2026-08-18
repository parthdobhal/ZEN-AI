"""
Sandboxed Project Workspace Manager.
"""

import os
from pathlib import Path
from typing import Any
from zen.config.constants import WORKSPACE_DIR
from zen.core.logger import logger
from zen.tools.guardrails import validate_path_safety


class WorkspaceManager:
    """Manages project directories and file operations strictly inside the workspace sandbox."""

    def __init__(self, root_workspace: Path = WORKSPACE_DIR) -> None:
        self.root_workspace = root_workspace
        self.root_workspace.mkdir(parents=True, exist_ok=True)

    def get_project_dir(self, project_name: str) -> Path:
        """Resolve and validate a project root path inside workspace."""
        clean_name = "".join(c for c in project_name if c.isalnum() or c in ("-", "_")).strip()
        if not clean_name:
            clean_name = "zen_project"
        project_path = (self.root_workspace / clean_name).resolve()
        return validate_path_safety(project_path, allow_read_only=False)

    def create_project(self, project_name: str) -> Path:
        """Create project root directory."""
        project_dir = self.get_project_dir(project_name)
        project_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created project sandbox at: [bold]{project_dir}[/bold]")
        return project_dir

    def write_file(self, project_name: str, relative_path: str, content: str) -> Path:
        """Write content to a file inside the project sandbox."""
        project_dir = self.get_project_dir(project_name)
        target_file = (project_dir / relative_path).resolve()
        
        # Ensure file does not escape project directory
        if project_dir not in target_file.parents and target_file != project_dir:
            raise ValueError(f"Path traversal blocked: '{relative_path}' escapes project directory.")

        target_file.parent.mkdir(parents=True, exist_ok=True)
        with open(target_file, "w", encoding="utf-8") as f:
            f.write(content)

        logger.debug(f"Wrote file: {target_file}")
        return target_file

    def read_file(self, project_name: str, relative_path: str) -> str:
        """Read text from a project file."""
        project_dir = self.get_project_dir(project_name)
        target_file = (project_dir / relative_path).resolve()

        if not target_file.exists():
            raise FileNotFoundError(f"File '{relative_path}' not found in project '{project_name}'.")

        with open(target_file, "r", encoding="utf-8", errors="replace") as f:
            return f.read()

    def list_project_files(self, project_name: str) -> list[str]:
        """List all files in the project, ignoring .venv and cache directories."""
        project_dir = self.get_project_dir(project_name)
        if not project_dir.exists():
            return []

        rel_paths = []
        for root, dirs, files in os.walk(project_dir):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("venv", ".venv", "__pycache__")]
            for f in files:
                full_path = Path(root) / f
                rel_path = full_path.relative_to(project_dir)
                rel_paths.append(rel_path.as_posix())

        return sorted(rel_paths)
