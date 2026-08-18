"""
Isolated Virtual Environment Manager for Coding Projects.
"""

import asyncio
from pathlib import Path
import subprocess
import sys
import venv
from zen.core.logger import logger


class ProjectEnvironment:
    """Manages an isolated Python virtualenv per coding project."""

    def __init__(self, project_dir: Path) -> None:
        self.project_dir = project_dir
        self.venv_dir = project_dir / ".venv"

    @property
    def python_executable(self) -> Path:
        """Returns the path to the virtualenv Python binary."""
        if sys.platform == "win32":
            return self.venv_dir / "Scripts" / "python.exe"
        return self.venv_dir / "bin" / "python"

    @property
    def pytest_executable(self) -> Path:
        """Returns the path to pytest binary in the virtualenv."""
        if sys.platform == "win32":
            return self.venv_dir / "Scripts" / "pytest.exe"
        return self.venv_dir / "bin" / "pytest"

    def exists(self) -> bool:
        """Check if virtualenv is initialized."""
        return self.python_executable.exists()

    async def create_venv(self) -> bool:
        """Create virtual environment if it does not already exist."""
        if self.exists():
            return True

        def _make_venv() -> None:
            logger.info(f"Creating isolated virtual environment in: {self.venv_dir}")
            builder = venv.EnvBuilder(with_pip=True, clear=False)
            builder.create(self.venv_dir)

        try:
            await asyncio.to_thread(_make_venv)
            return True
        except Exception as e:
            logger.error(f"Failed to create virtual environment: {e}")
            return False

    async def install_dependencies(self, packages: list[str] | None = None, req_file: Path | None = None) -> tuple[bool, str]:
        """Installs dependencies into the isolated project virtualenv."""
        if not self.exists():
            await self.create_venv()

        cmd = [str(self.python_executable), "-m", "pip", "install", "--quiet"]

        if req_file and req_file.exists():
            cmd.extend(["-r", str(req_file)])
        elif packages:
            cmd.extend(packages)
        else:
            return True, "No dependencies to install."

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(self.project_dir),
            )
            stdout, stderr = await process.communicate()
            success = process.returncode == 0
            output = (stdout.decode(errors="replace") + stderr.decode(errors="replace")).strip()
            return success, output
        except Exception as e:
            return False, f"pip install error: {e}"
