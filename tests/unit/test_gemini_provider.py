"""
Unit tests for Google Gemini Provider (Gemini 3.6 Flash) & Configuration.
"""

from pathlib import Path
from unittest.mock import AsyncMock, patch
import httpx
import pytest

from zen.brain.providers.gemini_provider import GeminiProvider
from zen.brain.router import create_ai_provider
from zen.config.settings import Settings
from zen.core.session import ChatMessage


def test_gemini_provider_default_model() -> None:
    provider = GeminiProvider(api_key="test_key")
    assert provider.model == "gemini-3.6-flash"


def test_settings_default_ai_model() -> None:
    # Verify default field value is gemini-3.6-flash
    assert Settings.model_fields["ai_model"].default == "gemini-3.6-flash"
    settings = Settings(_env_file=None)
    assert settings.ai_model == "gemini-3.6-flash"


def test_router_create_gemini_provider() -> None:
    settings = Settings(
        ZEN_AI_PROVIDER="gemini",
        ZEN_AI_MODEL="gemini-3.6-flash",
        GEMINI_API_KEY="test_key",
    )
    provider = create_ai_provider("gemini", settings=settings)
    assert isinstance(provider, GeminiProvider)
    assert provider.model == "gemini-3.6-flash"


def test_router_unknown_provider_fallback() -> None:
    settings = Settings(
        ZEN_AI_MODEL="gemini-3.6-flash",
        GEMINI_API_KEY="test_key",
    )
    # Cast to bypass literal type checking for unknown provider test
    provider = create_ai_provider("unknown_provider", settings=settings)  # type: ignore
    assert isinstance(provider, GeminiProvider)
    assert provider.model == "gemini-3.6-flash"


@pytest.mark.asyncio
async def test_gemini_36_flash_payload_compatibility() -> None:
    """Verify Gemini 3.6 Flash payload excludes deprecated generationConfig/temperature."""
    provider = GeminiProvider(api_key="test_api_key", model="gemini-3.6-flash")

    mock_gemini_response = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": "Hello, I am Gemini 3.6 Flash!"}],
                    "role": "model",
                },
                "finishReason": "STOP",
            }
        ]
    }

    mock_res = httpx.Response(
        status_code=200,
        json=mock_gemini_response,
        request=httpx.Request("POST", "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent"),
    )

    captured_requests = []

    async def mock_post(url: str, *args, **kwargs):
        captured_requests.append({"url": str(url), "json": kwargs.get("json")})
        return mock_res

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_client_post:
        mock_client_post.side_effect = mock_post

        messages = [ChatMessage(role="user", content="Hello!")]
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_system_info",
                    "description": "Get PC info",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]

        response = await provider.chat_complete(
            messages=messages,
            system_prompt="You are ZEN.",
            tools=tools,
            temperature=0.7,
        )

        assert response.content == "Hello, I am Gemini 3.6 Flash!"
        assert len(captured_requests) == 1

        sent_payload = captured_requests[0]["json"]
        sent_url = captured_requests[0]["url"]

        # Ensure correct endpoint and model
        assert "models/gemini-3.6-flash:generateContent" in sent_url
        assert "key=test_api_key" in sent_url

        # Ensure deprecated generationConfig / temperature is NOT sent
        assert "generationConfig" not in sent_payload
        assert "temperature" not in sent_payload
        assert "top_p" not in sent_payload
        assert "top_k" not in sent_payload
        assert "candidate_count" not in sent_payload
        assert "thinking_budget" not in sent_payload

        # Ensure valid Gemini 3.6 schema parts are sent
        assert "contents" in sent_payload
        assert "systemInstruction" in sent_payload
        assert "tools" in sent_payload
        assert sent_payload["tools"][0]["functionDeclarations"][0]["name"] == "get_system_info"


@pytest.mark.asyncio
async def test_gemini_tool_call_response_handling() -> None:
    """Verify GeminiProvider parses tool calls from Gemini response."""
    provider = GeminiProvider(api_key="test_api_key", model="gemini-3.6-flash")

    mock_tool_call_response = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "functionCall": {
                                "name": "web_search",
                                "args": {"query": "weather today"},
                            }
                        }
                    ],
                    "role": "model",
                }
            }
        ]
    }

    mock_res = httpx.Response(
        status_code=200,
        json=mock_tool_call_response,
        request=httpx.Request("POST", "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent"),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_res):
        messages = [ChatMessage(role="user", content="Search the weather")]
        response = await provider.chat_complete(messages)

        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].name == "web_search"
        assert response.tool_calls[0].arguments == {"query": "weather today"}
