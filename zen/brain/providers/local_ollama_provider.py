"""
Local Ollama Provider for offline, low-cost local models (e.g. Qwen, Llama).
"""

from typing import Any, AsyncIterator
import httpx

from zen.brain.provider_base import AIProviderBase, BrainDelta, BrainResponse, ToolCallRequest
from zen.core.logger import logger
from zen.core.session import ChatMessage


class OllamaProvider(AIProviderBase):
    """Integrates local Ollama models with OpenAI-compatible tool schemas."""

    name = "ollama"

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "qwen2.5-coder:7b",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def validate_credentials(self) -> bool:
        """Check if local Ollama daemon is active."""
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.get(f"{self.base_url}/api/tags")
                return res.status_code == 200
        except Exception:
            return False

    async def chat_complete(
        self,
        messages: list[ChatMessage],
        system_prompt: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
    ) -> BrainResponse:
        ollama_messages = []
        if system_prompt:
            ollama_messages.append({"role": "system", "content": system_prompt})
        for m in messages:
            ollama_messages.append({"role": m.role, "content": m.content})

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": ollama_messages,
            "stream": False,
            "options": {"temperature": temperature},
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                res = await client.post(f"{self.base_url}/api/chat", json=payload)
                if res.status_code != 200:
                    return BrainResponse(content=f"Ollama error: {res.text}")
                data = res.json()
                content = data.get("message", {}).get("content", "")
                return BrainResponse(content=content, raw_response=data)
        except Exception as e:
            return BrainResponse(content=f"Could not connect to Ollama at {self.base_url}: {e}")

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
        yield BrainDelta(is_done=True)
