"""
Asynchronous Test Runner and Subprocess Execution Engine.
"""

import asyncio
from dataclasses import dataclass
from pathlib import Path
import subprocess
from zen.coding.environment import ProjectEnvironment
from zen.core.logger import logger


@dataclass
class TestResult:
    """Outcome of running test suite or script."""
    passed: bool
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float


class TestRunner:
    """Executes tests or scripts within a project's isolated environment."""

    def __init__(self, project_dir: Path, timeout: float = 30.0) -> None:
        self.project_dir = project_dir
        self.env = ProjectEnvironment(project_dir)
        self.timeout = timeout

    async def run_pytest(self, test_path: str = "tests") -> TestResult:
        """Runs pytest inside the project sandbox."""
        start_time = asyncio.get_event_loop().time()
        
        # Use pytest in venv or python -m unittest
        if self.env.pytest_executable.exists():
            cmd = [str(self.env.pytest_executable), test_path, "-v"]
        elif self.env.python_executable.exists():
            cmd = [str(self.env.python_executable), "-m", "unittest", "discover", "-s", test_path]
        else:
            # Fallback to system python running unittest
            cmd = ["python", "-m", "unittest", "discover", "-s", str(self.project_dir / test_path)]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(self.project_dir),
            )
            try:
                stdout_b, stderr_b = await asyncio.wait_for(process.communicate(), timeout=self.timeout)
            except asyncio.TimeoutError:
                process.kill()
                return TestResult(
                    passed=False,
                    exit_code=-1,
                    stdout="",
                    stderr=f"Test execution timed out after {self.timeout} seconds.",
                    duration_seconds=self.timeout,
                )

            duration = round(asyncio.get_event_loop().time() - start_time, 2)
            stdout = stdout_b.decode(errors="replace")
            stderr = stderr_b.decode(errors="replace")
            passed = process.returncode == 0

            return TestResult(
                passed=passed,
                exit_code=process.returncode or 0,
                stdout=stdout,
                stderr=stderr,
                duration_seconds=duration,
            )
        except Exception as e:
            return TestResult(
                passed=False,
                exit_code=-1,
                stdout="",
                stderr=f"Test runner execution error: {e}",
                duration_seconds=0.0,
            )

    async def run_script(self, script_path: str, args: list[str] | None = None) -> TestResult:
        """Executes a python script inside the sandbox."""
        start_time = asyncio.get_event_loop().time()
        python_bin = str(self.env.python_executable) if self.env.exists() else "python"
        cmd = [python_bin, script_path] + (args or [])

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(self.project_dir),
            )
            try:
                stdout_b, stderr_b = await asyncio.wait_for(process.communicate(), timeout=self.timeout)
            except asyncio.TimeoutError:
                process.kill()
                return TestResult(
                    passed=False,
                    exit_code=-1,
                    stdout="",
                    stderr=f"Script execution timed out after {self.timeout} seconds.",
                    duration_seconds=self.timeout,
                )

            duration = round(asyncio.get_event_loop().time() - start_time, 2)
            stdout = stdout_b.decode(errors="replace")
            stderr = stderr_b.decode(errors="replace")
            passed = process.returncode == 0

            return TestResult(
                passed=passed,
                exit_code=process.returncode or 0,
                stdout=stdout,
                stderr=stderr,
                duration_seconds=duration,
            )
        except Exception as e:
            return TestResult(
                passed=False,
                exit_code=-1,
                stdout="",
                stderr=f"Script runner error: {e}",
                duration_seconds=0.0,
            )
