"""
Application & Browser Launcher Tool for Windows.
"""

import os
import subprocess
import webbrowser
from pydantic import BaseModel, Field
from zen.config.constants import RISK_SAFE_EXECUTE
from zen.core.logger import logger
from zen.tools.base import BaseTool, ToolResult

# Mapping of common friendly names to Windows executables or URI protocols
KNOWN_APPS: dict[str, list[str]] = {
    "notepad": ["notepad.exe"],
    "calculator": ["calc.exe"],
    "calc": ["calc.exe"],
    "explorer": ["explorer.exe"],
    "settings": ["ms-settings:"],
    "vscode": ["code"],
    "vs code": ["code"],
    "terminal": ["wt.exe", "cmd.exe"],
    "cmd": ["cmd.exe"],
    "powershell": ["powershell.exe"],
    "paint": ["mspaint.exe"],
    "task manager": ["taskmgr.exe"],
    "taskmgr": ["taskmgr.exe"],
}


class LaunchAppParams(BaseModel):
    app_name: str = Field(description="Name of the application (e.g., 'notepad', 'calc', 'vscode', 'spotify', 'explorer')")
    arguments: str | None = Field(default=None, description="Optional command-line arguments to pass to the application")


class OpenUrlParams(BaseModel):
    url: str = Field(description="Web URL to open in the user's default browser (e.g. 'https://github.com')")


class LaunchAppTool(BaseTool):
    """Launches a desktop application or Windows system tool."""

    name = "launch_application"
    description = "Opens a Windows application such as Notepad, Calculator, VS Code, Spotify, File Explorer, or Settings."
    risk_level = RISK_SAFE_EXECUTE
    parameters_schema = LaunchAppParams

    async def execute(self, params: LaunchAppParams, context: None = None) -> ToolResult:
        app_key = params.app_name.lower().strip()
        
        # 1. Check known mappings
        if app_key in KNOWN_APPS:
            candidates = KNOWN_APPS[app_key]
            for cmd in candidates:
                try:
                    if cmd.startswith("ms-"):
                        # Protocol URI
                        os.startfile(cmd)
                        return ToolResult.ok(message=f"Opened Windows Settings / Protocol: {cmd}")
                    else:
                        full_cmd = [cmd]
                        if params.arguments:
                            full_cmd.extend(params.arguments.split())
                        subprocess.Popen(full_cmd, shell=True)
                        return ToolResult.ok(message=f"Launched application: {params.app_name}")
                except Exception as e:
                    logger.debug(f"Failed candidate {cmd}: {e}")
                    continue

        # 2. Try generic os.startfile for Windows registered programs
        try:
            os.startfile(params.app_name)
            return ToolResult.ok(message=f"Opened {params.app_name}")
        except Exception:
            pass

        # 3. Try subprocess execution
        try:
            cmd = [params.app_name]
            if params.arguments:
                cmd.extend(params.arguments.split())
            subprocess.Popen(cmd, shell=True)
            return ToolResult.ok(message=f"Launched {params.app_name}")
        except Exception as e:
            return ToolResult.fail(f"Could not launch application '{params.app_name}': {e}")


class OpenUrlTool(BaseTool):
    """Opens a website in the user's default web browser."""

    name = "open_url"
    description = "Opens a web address in the user's default browser."
    risk_level = RISK_SAFE_EXECUTE
    parameters_schema = OpenUrlParams

    async def execute(self, params: OpenUrlParams, context: None = None) -> ToolResult:
        url = params.url.strip()
        if not (url.startswith("http://") or url.startswith("https://")):
            url = "https://" + url
        try:
            webbrowser.open(url)
            return ToolResult.ok(message=f"Opened URL in browser: {url}")
        except Exception as e:
            return ToolResult.fail(f"Failed to open URL '{url}': {e}")
