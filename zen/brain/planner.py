"""
Multi-step task planner for complex user instructions.
"""

from typing import Any
from pydantic import BaseModel, Field
from zen.brain.provider_base import AIProviderBase
from zen.core.session import ChatMessage


class PlanStep(BaseModel):
    step_number: int
    description: str
    tool_to_use: str | None = None
    expected_outcome: str


class TaskPlan(BaseModel):
    goal: str
    steps: list[PlanStep] = Field(default_factory=list)
    estimated_complexity: str = "medium"


class TaskPlanner:
    """Generates execution plans before executing multi-tool workflows."""

    def __init__(self, provider: AIProviderBase) -> None:
        self.provider = provider

    async def generate_plan(self, user_request: str, available_tools_summary: str) -> TaskPlan:
        """Create a structured step-by-step plan for the user's objective."""
        prompt = f"""You are the task planning engine for ZEN.
Given the following user request and available tools, produce a concise step-by-step plan.

USER REQUEST:
{user_request}

AVAILABLE TOOLS:
{available_tools_summary}

Respond with a clear list of steps needed to achieve the goal safely and accurately.
"""
        messages = [ChatMessage(role="user", content=prompt)]
        resp = await self.provider.chat_complete(messages, temperature=0.2)
        
        # Simple step extraction
        steps = []
        lines = resp.content.split("\n")
        idx = 1
        for line in lines:
            line_str = line.strip()
            if line_str and (line_str[0].isdigit() or line_str.startswith("-")):
                clean_text = line_str.lstrip("0123456789.-* ")
                if clean_text:
                    steps.append(
                        PlanStep(
                            step_number=idx,
                            description=clean_text,
                            expected_outcome="Proceed with task execution",
                        )
                    )
                    idx += 1

        if not steps:
            steps.append(
                PlanStep(
                    step_number=1,
                    description=f"Fulfill request: {user_request}",
                    expected_outcome="Success",
                )
            )

        return TaskPlan(goal=user_request, steps=steps)
