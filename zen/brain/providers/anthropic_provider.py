"""
Anthropic Claude AI Provider Implementation using async HTTPX.
"""

from typing import Any, AsyncIterator
import httpx

from zen.brain.provider_base import AIProviderBase, BrainDelta, BrainResponse, ToolCallRequest
from zen.core.logger import logger
from zen.core.session import ChatMessage


class AnthropicProvider(AIProviderBase):
    """Integrates Anthropic Claude models with native tool use."""

    name = "anthropic"

    def __init__(self, api_key: str | None = None, model: str = "claude-3-5-sonnet-20241022") -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.anthropic.com/v1"

    async def validate_credentials(self) -> bool:
        return bool(self.api_key and len(self.api_key) > 10)

    def _convert_tools(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        anthropic_tools = []
        for t in tools:
            fn = t.get("function", {})
            anthropic_tools.append(
                {
                    "name": fn.get("name"),
                    "description": fn.get("description", ""),
                    "input_schema": fn.get("parameters", {}),
                }
            )
        return anthropic_tools

    def _convert_messages(self, messages: list[ChatMessage]) -> list[dict[str, Any]]:
        anthropic_messages = []
        for msg in messages:
            if msg.role == "system":
                continue  # Passed via top-level system parameter

            if msg.role == "tool":
                anthropic_messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": msg.tool_call_id or "tool_call",
                                "content": msg.content,
                            }
                        ],
                    }
                )
                continue

            content_blocks = []
            if msg.content:
                content_blocks.append({"type": "text", "text": msg.content})

            if msg.tool_calls:
                for tc in msg.tool_calls:
                    content_blocks.append(
                        {
                            "type": "tool_use",
                            "id": tc.get("id", "tool_0"),
                            "name": tc.get("name"),
                            "input": tc.get("arguments", {}),
                        }
                    )

            role = "assistant" if msg.role == "assistant" else "user"
            anthropic_messages.append({"role": role, "content": content_blocks or msg.content})

        return anthropic_messages

    async def chat_complete(
        self,
        messages: list[ChatMessage],
        system_prompt: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
    ) -> BrainResponse:
        if not self.api_key:
            return BrainResponse(content="Error: ANTHROPIC_API_KEY is not configured in .env")

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": self._convert_messages(messages),
            "temperature": temperature,
        }
        if system_prompt:
            payload["system"] = system_prompt
        if tools:
            payload["tools"] = self._convert_tools(tools)

        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(f"{self.base_url}/messages", headers=headers, json=payload)
            if res.status_code != 200:
                err = f"Anthropic API Error ({res.status_code}): {res.text}"
                logger.error(err)
                return BrainResponse(content=err)

            data = res.json()
            contents = []
            tool_calls = []
            for block in data.get("content", []):
                if block.get("type") == "text":
                    contents.append(block.get("text", ""))
                elif block.get("type") == "tool_use":
                    tool_calls.append(
                        ToolCallRequest(
                            id=block.get("id", "call_0"),
                            name=block.get("name", ""),
                            arguments=block.get("input", {}),
                        )
                    )

            return BrainResponse(
                content="".join(contents),
                tool_calls=tool_calls,
                raw_response=data,
            )

    async def stream_chat(
        self,
        messages: list[ChatMessage],
        system_prompt: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
    ) -> AsyncIterator[BrainDelta]:
        resp = await self.chat_complete(messages, system_prompt, tools, temperature)
        if resp.content:
            yield BrainDelta(content_delta=resp.content)
        for tc in resp.tool_calls:
            yield BrainDelta(tool_call_delta=tc)
        yield BrainDelta(is_done=True)
