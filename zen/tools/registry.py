"""
Dynamic Tool Registry with validation and permission integration.
"""

import json
from typing import Any
from pydantic import ValidationError

from zen.core.events import EventType, event_bus
from zen.core.logger import logger
from zen.tools.base import BaseTool, ToolResult
from zen.tools.permissions import ConfirmationCallback, PermissionDeniedError, PermissionEngine


class ToolRegistry:
    """Central registry of all executable tools in ZEN."""

    def __init__(self, permission_engine: PermissionEngine | None = None) -> None:
        self._tools: dict[str, BaseTool] = {}
        self.permission_engine = permission_engine or PermissionEngine()

    def register(self, tool: BaseTool) -> None:
        """Register a tool instance."""
        if tool.name in self._tools:
            logger.warning(f"Overwriting existing tool registration for '{tool.name}'")
        self._tools[tool.name] = tool
        logger.debug(f"Registered tool: [bold]{tool.name}[/bold] ({tool.risk_level})")

    def get(self, name: str) -> BaseTool | None:
        """Retrieve tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> list[BaseTool]:
        """List all registered tools."""
        return list(self._tools.values())

    def get_function_schemas(self) -> list[dict[str, Any]]:
        """Export all registered tools in OpenAI/Gemini JSON function schema format."""
        return [tool.get_json_schema() for tool in self._tools.values()]

    async def execute(
        self,
        name: str,
        arguments: dict[str, Any] | str,
        context: Any = None,
        confirm_callback: ConfirmationCallback | None = None,
    ) -> ToolResult:
        """
        Validate parameters, verify permissions, execute tool, and record audit log.
        """
        tool = self.get(name)
        if not tool:
            return ToolResult.fail(f"Tool '{name}' is not registered.")

        # Parse string arguments if received from LLM
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments) if arguments.strip() else {}
            except json.JSONDecodeError as e:
                return ToolResult.fail(f"Invalid JSON arguments for tool '{name}': {e}")

        # 1. Parameter Validation via Pydantic schema
        try:
            validated_params = tool.parameters_schema.model_validate(arguments)
        except ValidationError as e:
            err_msg = f"Parameter validation failed for '{name}': {e}"
            logger.error(err_msg)
            return ToolResult.fail(err_msg)

        # 2. Permission and Safety Authorization
        try:
            await self.permission_engine.verify_and_authorize(
                tool_name=name,
                risk_level=tool.risk_level,
                parameters=arguments,
                confirm_callback=confirm_callback,
            )
        except PermissionDeniedError as e:
            return ToolResult.fail(str(e))
        except Exception as e:
            return ToolResult.fail(f"Authorization error for '{name}': {e}")

        # 3. Tool Execution
        await event_bus.emit(EventType.TOOL_STARTED, {"tool_name": name, "parameters": arguments})
        try:
            result = await tool.execute(validated_params, context)
            status = "SUCCESS" if result.success else "FAILED"
            self.permission_engine.log_execution_result(
                tool_name=name,
                risk_level=tool.risk_level,
                status=status,
                parameters=arguments,
                output_preview=result.output_message or str(result.data),
            )
            await event_bus.emit(
                EventType.TOOL_FINISHED,
                {"tool_name": name, "success": result.success, "output": result.output_message},
            )
            return result
        except Exception as e:
            logger.error(f"Execution error in tool '{name}': {e}", exc_info=True)
            self.permission_engine.log_execution_result(
                tool_name=name,
                risk_level=tool.risk_level,
                status="EXCEPTION",
                parameters=arguments,
                output_preview=str(e),
            )
            await event_bus.emit(EventType.TOOL_FAILED, {"tool_name": name, "error": str(e)})
            return ToolResult.fail(f"Tool execution exception: {e}")


# Global tool registry
tool_registry = ToolRegistry()
