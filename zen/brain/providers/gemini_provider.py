"""
Google Gemini AI Provider Implementation using async HTTPX.
"""

import json
from typing import Any, AsyncIterator
import httpx

from zen.brain.provider_base import AIProviderBase, BrainDelta, BrainResponse, ToolCallRequest
from zen.core.logger import logger
from zen.core.session import ChatMessage


class GeminiProvider(AIProviderBase):
    """Integrates Google's Gemini models via REST API with tool calling."""

    name = "gemini"

    def __init__(self, api_key: str | None = None, model: str = "gemini-3.6-flash") -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"

    async def validate_credentials(self) -> bool:
        """Check if Gemini API Key is present and valid."""
        if not self.api_key:
            return False
        url = f"{self.base_url}/models/{self.model}?key={self.api_key}"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(url)
                return res.status_code == 200
        except Exception as e:
            logger.error(f"Gemini credential validation failed: {e}")
            return False

    def _convert_messages_to_gemini(
        self,
        messages: list[ChatMessage],
        system_prompt: str | None = None,
    ) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        """Format generic ChatMessage items to Gemini content format."""
        gemini_contents = []
        system_instruction = None

        if system_prompt:
            system_instruction = {"parts": [{"text": system_prompt}]}

        for msg in messages:
            role = "user" if msg.role in ("user", "system") else "model"
            parts: list[dict[str, Any]] = []

            if msg.role == "tool":
                # Gemini tool response format
                gemini_contents.append(
                    {
                        "role": "user",
                        "parts": [
                            {
                                "functionResponse": {
                                    "name": msg.name or "tool",
                                    "response": {"result": msg.content},
                                }
                            }
                        ],
                    }
                )
                continue

            if msg.content:
                parts.append({"text": msg.content})

            if msg.tool_calls:
                for tc in msg.tool_calls:
                    parts.append(
                        {
                            "functionCall": {
                                "name": tc.get("name"),
                                "args": tc.get("arguments", {}),
                            }
                        }
                    )

            if parts:
                gemini_contents.append({"role": role, "parts": parts})

        return system_instruction, gemini_contents

    def _convert_tools_to_gemini(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert OpenAI-style function definitions to Gemini function declarations."""
        declarations = []
        for tool in tools:
            fn = tool.get("function", {})
            declarations.append(
                {
                    "name": fn.get("name"),
                    "description": fn.get("description", ""),
                    "parameters": fn.get("parameters", {}),
                }
            )
        return [{"functionDeclarations": declarations}]

    async def chat_complete(
        self,
        messages: list[ChatMessage],
        system_prompt: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
    ) -> BrainResponse:
        """Call Gemini API generateContent."""
        if not self.api_key:
            return BrainResponse(content="Error: GEMINI_API_KEY is not configured in .env")

        system_instruction, contents = self._convert_messages_to_gemini(messages, system_prompt)
        payload: dict[str, Any] = {
            "contents": contents,
        }

        if system_instruction:
            payload["systemInstruction"] = system_instruction

        if tools:
            payload["tools"] = self._convert_tools_to_gemini(tools)

        url = f"{self.base_url}/models/{self.model}:generateContent?key={self.api_key}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(url, json=payload)
            if res.status_code != 200:
                err_text = res.text
                logger.error(f"Gemini API Error ({res.status_code}): {err_text}")
                return BrainResponse(content=f"Gemini API Error: {res.status_code} - {err_text}")

            data = res.json()
            candidates = data.get("candidates", [])
            if not candidates:
                return BrainResponse(content="No response generated from Gemini.")

            candidate = candidates[0]
            parts = candidate.get("content", {}).get("parts", [])
            text_chunks = []
            tool_calls = []

            for part in parts:
                if "text" in part:
                    text_chunks.append(part["text"])
                elif "functionCall" in part:
                    fn_call = part["functionCall"]
                    tool_calls.append(
                        ToolCallRequest(
                            id=fn_call.get("name", "call_0"),
                            name=fn_call.get("name", ""),
                            arguments=fn_call.get("args", {}),
                        )
                    )

            return BrainResponse(
                content="".join(text_chunks),
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
        """Streaming chat completion using streamGenerateContent."""
        # For simplicity and robust tool execution, execute chat_complete and stream result
        resp = await self.chat_complete(messages, system_prompt, tools, temperature)
        if resp.content:
            yield BrainDelta(content_delta=resp.content)
        for tc in resp.tool_calls:
            yield BrainDelta(tool_call_delta=tc)
        yield BrainDelta(is_done=True)
