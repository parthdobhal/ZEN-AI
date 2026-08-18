"""
Brain Router and Provider Factory for ZEN.
"""

from typing import Literal
from zen.brain.provider_base import AIProviderBase
from zen.brain.providers.anthropic_provider import AnthropicProvider
from zen.brain.providers.gemini_provider import GeminiProvider
from zen.brain.providers.local_ollama_provider import OllamaProvider
from zen.brain.providers.openai_provider import OpenAIProvider
from zen.config.settings import Settings, get_settings
from zen.core.logger import logger
from zen.memory.memory_manager import MemoryManager

ZEN_BASE_SYSTEM_PROMPT = """You are ZEN, a voice-first personal AI computer assistant engineered for Windows.
Your goal is to be exceptionally helpful, accurate, friendly, and efficient.

CORE PRINCIPLES:
1. VOICE-FIRST SYNTHESIS: Keep spoken explanations direct, clear, and natural. Avoid excessively long markdown dumps when a concise answer is better.
2. SAFETY & EXPLICIT TOOLS: When the user asks you to inspect the computer, search files, open apps, search the web, or build code, ALWAYS use your registered tools.
3. ADAPTIVE LEARNING: Follow learned rules and user preferences strictly.
4. HONESTY: If you are unsure or lack current information, use the web research tool rather than guessing.
5. CODING: When asked to build or fix software, use the dedicated coding agent tools to create files, test in virtual environments, and fix errors automatically.
"""


def create_ai_provider(
    provider_name: Literal["gemini", "openai", "anthropic", "ollama"] | None = None,
    settings: Settings | None = None,
) -> AIProviderBase:
    """Factory creating the appropriate AI provider instance."""
    cfg = settings or get_settings()
    target_provider = provider_name or cfg.ai_provider

    if target_provider == "gemini":
        return GeminiProvider(api_key=cfg.gemini_api_key, model=cfg.ai_model)
    elif target_provider == "openai":
        return OpenAIProvider(api_key=cfg.openai_api_key, model=cfg.ai_model)
    elif target_provider == "anthropic":
        return AnthropicProvider(api_key=cfg.anthropic_api_key, model=cfg.ai_model)
    elif target_provider == "ollama":
        return OllamaProvider(base_url=cfg.ollama_base_url, model=cfg.ollama_model)
    else:
        logger.warning(f"Unknown provider '{target_provider}', falling back to Gemini.")
        return GeminiProvider(api_key=cfg.gemini_api_key, model=cfg.ai_model)


def build_system_prompt(
    memory_manager: MemoryManager | None = None,
    active_project: str | None = None,
) -> str:
    """Construct full system prompt with dynamic memory injection."""
    prompt = ZEN_BASE_SYSTEM_PROMPT
    if memory_manager:
        memory_injection = memory_manager.build_memory_prompt_injection(active_project)
        if memory_injection.strip():
            prompt += f"\n\n--- PERSISTENT CONTEXT & MEMORY ---\n{memory_injection}\n-----------------------------------"
    return prompt
