"""
Autonomous Coding Agent & Self-Debugging Loop Engine.
"""

import json
from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field

from zen.brain.provider_base import AIProviderBase
from zen.coding.environment import ProjectEnvironment
from zen.coding.error_analyzer import ErrorAnalyzer
from zen.coding.test_runner import TestRunner
from zen.coding.workspace_manager import WorkspaceManager
from zen.config.constants import RISK_SAFE_EXECUTE
from zen.core.events import EventType, event_bus
from zen.core.logger import logger
from zen.core.session import ChatMessage
from zen.tools.base import BaseTool, ToolResult


class CodingProjectParams(BaseModel):
    project_name: str = Field(description="Name of the project directory (e.g., 'water_tracker', 'markdown_parser')")
    requirement: str = Field(description="Detailed natural-language description of what the project should do and include")
    max_fix_iterations: int = Field(default=5, ge=1, le=8, description="Max auto-debugging cycles")


class RunTestsParams(BaseModel):
    project_name: str = Field(description="Name of the project to test")


class CodingAgent:
    """Orchestrates autonomous project generation, testing, and error-repair loops."""

    def __init__(
        self,
        ai_provider: AIProviderBase,
        workspace_manager: WorkspaceManager | None = None,
    ) -> None:
        self.provider = ai_provider
        self.workspace = workspace_manager or WorkspaceManager()

    async def build_project(
        self,
        project_name: str,
        requirement: str,
        max_iterations: int = 5,
    ) -> dict[str, Any]:
        """Full autonomous development loop: Plan -> Scaffold -> Write -> Run -> Fix -> Verify."""
        logger.info(f"Starting autonomous coding project: [bold]{project_name}[/bold]")
        await event_bus.emit(
            EventType.CODING_PROJECT_STARTED,
            {"project_name": project_name, "requirement": requirement},
        )

        project_dir = self.workspace.create_project(project_name)
        env = ProjectEnvironment(project_dir)
        test_runner = TestRunner(project_dir)

        # 1. Ask Brain to plan and write project files as JSON
        planning_prompt = f"""You are the ZEN Autonomous Coding Engine.
Build a complete, clean, tested Python project named '{project_name}' based on this requirement:

REQUIREMENT:
{requirement}

You must provide a JSON response in the following format:
{{
    "summary": "Brief summary of the project architecture",
    "dependencies": ["list", "of", "pip", "packages", "e.g.", "pydantic"],
    "files": {{
        "requirements.txt": "dependencies here",
        "{project_name}/__init__.py": "",
        "{project_name}/main.py": "code here",
        "tests/__init__.py": "",
        "tests/test_{project_name}.py": "complete pytest or unittest tests here"
    }}
}}

Make sure the tests are comprehensive and directly runnable with `pytest` or `unittest`.
Output ONLY valid JSON.
"""
        messages = [ChatMessage(role="user", content=planning_prompt)]
        resp = await self.provider.chat_complete(messages, temperature=0.2)

        # Parse generated JSON
        try:
            clean_json = resp.content.strip()
            if "```json" in clean_json:
                clean_json = clean_json.split("```json")[1].split("```")[0].strip()
            elif "```" in clean_json:
                clean_json = clean_json.split("```")[1].split("```")[0].strip()

            project_plan = json.loads(clean_json)
        except Exception as e:
            logger.error(f"Failed to parse AI project plan JSON: {e}\nRaw output: {resp.content}")
            return {
                "success": False,
                "error": f"Failed to generate structured code plan: {e}",
                "project_path": str(project_dir),
            }

        # 2. Write initial project files
        files_dict = project_plan.get("files", {})
        for rel_path, code in files_dict.items():
            self.workspace.write_file(project_name, rel_path, code)

        # 3. Create isolated virtualenv & install dependencies
        await env.create_venv()
        deps = project_plan.get("dependencies", [])
        if "pytest" not in deps:
            deps.append("pytest")

        logger.info(f"Installing dependencies for {project_name}: {deps}")
        await env.install_dependencies(packages=deps)

        # 4. Iterative Test & Auto-Fix Loop
        current_iteration = 0
        test_history = []
        is_verified = False

        while current_iteration < max_iterations:
            current_iteration += 1
            logger.info(f"Running verification test cycle {current_iteration}/{max_iterations} for {project_name}...")
            
            test_res = await test_runner.run_pytest("tests")
            await event_bus.emit(
                EventType.CODING_TEST_RUN,
                {
                    "project_name": project_name,
                    "iteration": current_iteration,
                    "passed": test_res.passed,
                    "stdout": test_res.stdout,
                },
            )

            test_history.append(
                {
                    "iteration": current_iteration,
                    "passed": test_res.passed,
                    "stdout": test_res.stdout,
                    "stderr": test_res.stderr,
                }
            )

            if test_res.passed:
                is_verified = True
                logger.info(f"[green]Project {project_name} passed all tests on cycle {current_iteration}![/green]")
                await event_bus.emit(EventType.CODING_VERIFIED, {"project_name": project_name})
                break

            # If tests failed, analyze error and generate targeted fix
            diagnostic = ErrorAnalyzer.analyze(test_res.stderr, test_res.stdout)
            logger.warning(
                f"Test failure in cycle {current_iteration}: {diagnostic.exception_type} - {diagnostic.message}"
            )

            # Get current files to give context to Brain
            current_files_content = {}
            for pf in self.workspace.list_project_files(project_name):
                current_files_content[pf] = self.workspace.read_file(project_name, pf)

            fix_prompt = f"""You are the ZEN Self-Debugging Engine.
The tests failed for project '{project_name}'. Please diagnose and fix the bugs.

FAILURE TRACEBACK:
{diagnostic.raw_traceback}

CURRENT PROJECT FILES:
{json.dumps(current_files_content, indent=2)}

Provide a JSON object containing the updated or replacement files to fix the issues:
{{
    "diagnosis": "Explanation of what went wrong",
    "updated_files": {{
        "path/to/file.py": "full fixed code"
    }}
}}
Output ONLY valid JSON.
"""
            fix_msg = [ChatMessage(role="user", content=fix_prompt)]
            fix_resp = await self.provider.chat_complete(fix_msg, temperature=0.1)

            try:
                clean_fix_json = fix_resp.content.strip()
                if "```json" in clean_fix_json:
                    clean_fix_json = clean_fix_json.split("```json")[1].split("```")[0].strip()
                elif "```" in clean_fix_json:
                    clean_fix_json = clean_fix_json.split("```")[1].split("```")[0].strip()

                fix_data = json.loads(clean_fix_json)
                updated_files = fix_data.get("updated_files", {})
                logger.info(f"Applying auto-fixes for files: {list(updated_files.keys())}")
                await event_bus.emit(
                    EventType.CODING_AUTO_FIX,
                    {"project_name": project_name, "files": list(updated_files.keys())},
                )

                for rel_path, code in updated_files.items():
                    self.workspace.write_file(project_name, rel_path, code)

            except Exception as e:
                logger.error(f"Failed to apply auto-fix: {e}")
                break

        final_files = self.workspace.list_project_files(project_name)
        return {
            "success": is_verified,
            "project_name": project_name,
            "project_path": str(project_dir),
            "files_created": final_files,
            "iterations_used": current_iteration,
            "summary": project_plan.get("summary", ""),
            "test_history": test_history,
        }


class CreateCodingProjectTool(BaseTool):
    """Tool exposing the Autonomous Coding Agent to the AI Brain."""

    name = "create_coding_project"
    description = "Autonomously plans, scaffolds, codes, runs tests in a sandbox, and auto-fixes Python software projects."
    risk_level = RISK_SAFE_EXECUTE
    parameters_schema = CodingProjectParams

    def __init__(self, coding_agent: CodingAgent) -> None:
        self.coding_agent = coding_agent

    async def execute(self, params: CodingProjectParams, context: Any = None) -> ToolResult:
        result = await self.coding_agent.build_project(
            project_name=params.project_name,
            requirement=params.requirement,
            max_iterations=params.max_fix_iterations,
        )

        if result["success"]:
            msg = (
                f"Successfully built and verified project '{params.project_name}' in {result['iterations_used']} cycle(s)!\n"
                f"Location: {result['project_path']}\n"
                f"Files:\n" + "\n".join(f"- {f}" for f in result["files_created"]) + "\n\n"
                f"Summary: {result.get('summary', '')}"
            )
            return ToolResult.ok(data=result, message=msg)
        else:
            msg = (
                f"Project '{params.project_name}' scaffolded at {result['project_path']}, "
                f"but tests did not pass after {result['iterations_used']} iterations."
            )
            return ToolResult.fail(msg)


class RunProjectTestsTool(BaseTool):
    """Tool allowing the Brain to run tests on an existing project."""

    name = "run_project_tests"
    description = "Executes the test suite for a project in workspace and returns pass/fail and stack traces."
    risk_level = RISK_SAFE_EXECUTE
    parameters_schema = RunTestsParams

    def __init__(self, workspace: WorkspaceManager | None = None) -> None:
        self.workspace = workspace or WorkspaceManager()

    async def execute(self, params: RunTestsParams, context: Any = None) -> ToolResult:
        project_dir = self.workspace.get_project_dir(params.project_name)
        if not project_dir.exists():
            return ToolResult.fail(f"Project '{params.project_name}' not found in workspace.")

        runner = TestRunner(project_dir)
        test_res = await runner.run_pytest("tests")

        status = "PASSED" if test_res.passed else "FAILED"
        msg = f"Tests {status} (duration: {test_res.duration_seconds}s):\n{test_res.stdout}\n{test_res.stderr}"
        return ToolResult.ok(data=test_res, message=msg)
