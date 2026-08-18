"""
OpenAI & OpenAI-compatible AI Provider Implementation using async HTTPX.
"""

import json
from typing import Any, AsyncIterator
import httpx

from zen.brain.provider_base import AIProviderBase, BrainDelta, BrainResponse, ToolCallRequest
from zen.core.logger import logger
from zen.core.session import ChatMessage


class OpenAIProvider(AIProviderBase):
    """Integrates OpenAI and OpenAI-compatible endpoints with full tool calling."""

    name = "openai"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gpt-4o",
        base_url: str = "https://api.openai.com/v1",
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")

    async def validate_credentials(self) -> bool:
        """Check API key validity against /v1/models endpoint."""
        if not self.api_key:
            return False
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(f"{self.base_url}/models", headers=headers)
                return res.status_code == 200
        except Exception as e:
            logger.error(f"OpenAI credential validation failed: {e}")
            return False

    def _format_messages(
        self,
        messages: list[ChatMessage],
        system_prompt: str | None = None,
    ) -> list[dict[str, Any]]:
        formatted: list[dict[str, Any]] = []
        if system_prompt:
            formatted.append({"role": "system", "content": system_prompt})

        for msg in messages:
            entry: dict[str, Any] = {"role": msg.role, "content": msg.content or ""}
            if msg.name:
                entry["name"] = msg.name
            if msg.tool_call_id:
                entry["tool_call_id"] = msg.tool_call_id
            if msg.tool_calls:
                entry["tool_calls"] = [
                    {
                        "id": tc.get("id", "call_0"),
                        "type": "function",
                        "function": {
                            "name": tc.get("name"),
                            "arguments": json.dumps(tc.get("arguments", {})),
                        },
                    }
                    for tc in msg.tool_calls
                ]
            formatted.append(entry)
        return formatted

    async def chat_complete(
        self,
        messages: list[ChatMessage],
        system_prompt: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
    ) -> BrainResponse:
        """Execute chat completion request."""
        if not self.api_key:
            return BrainResponse(content="Error: OPENAI_API_KEY is not configured in .env")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": self._format_messages(messages, system_prompt),
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
            if res.status_code != 200:
                err_msg = f"OpenAI API error ({res.status_code}): {res.text}"
                logger.error(err_msg)
                return BrainResponse(content=err_msg)

            data = res.json()
            choice = data.get("choices", [{}])[0]
            message_obj = choice.get("message", {})
            content = message_obj.get("content") or ""

            tool_calls = []
            for tc in message_obj.get("tool_calls", []):
                fn = tc.get("function", {})
                fn_name = fn.get("name", "")
                raw_args = fn.get("arguments", "{}")
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except Exception:
                    args = {}
                tool_calls.append(ToolCallRequest(id=tc.get("id", "call_0"), name=fn_name, arguments=args))

            return BrainResponse(
                content=content,
                tool_calls=tool_calls,
                raw_response=data,
                finish_reason=choice.get("finish_reason", "stop"),
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
