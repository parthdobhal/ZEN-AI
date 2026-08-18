"""
BaseTool abstract definition and ToolResult schema.
"""

from abc import ABC, abstractmethod
from typing import Any, Type
from pydantic import BaseModel, Field
from zen.config.constants import RISK_SAFE_EXECUTE


class ToolResult(BaseModel):
    """Encapsulates the outcome of a tool execution."""
    success: bool = True
    data: Any = None
    error: str | None = None
    output_message: str = ""

    @classmethod
    def ok(cls, data: Any = None, message: str = "") -> "ToolResult":
        return cls(success=True, data=data, output_message=message or str(data))

    @classmethod
    def fail(cls, error: str) -> "ToolResult":
        return cls(success=False, error=error, output_message=f"Error: {error}")


class BaseTool(ABC):
    """Abstract base class for all ZEN tools."""

    name: str
    description: str
    risk_level: str = RISK_SAFE_EXECUTE
    parameters_schema: Type[BaseModel]

    @abstractmethod
    async def execute(self, params: Any, context: Any = None) -> ToolResult:
        """Asynchronously executes the tool logic with validated params."""
        pass

    def get_json_schema(self) -> dict[str, Any]:
        """Generate OpenAI/Gemini compatible JSON schema for the tool."""
        model_schema = self.parameters_schema.model_json_schema()
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": model_schema.get("properties", {}),
                    "required": model_schema.get("required", []),
                },
            },
        }
