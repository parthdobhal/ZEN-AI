"""
Pydantic typed application settings and configuration manager for ZEN.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from zen.config.constants import ROOT_DIR, WORKSPACE_DIR, DATA_DIR


class Settings(BaseSettings):
    """Global configuration settings for ZEN assistant."""

    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Core AI Provider Settings
    ai_provider: Literal["gemini", "openai", "anthropic", "ollama"] = Field(
        default="gemini",
        alias="ZEN_AI_PROVIDER",
        description="The active LLM provider backend",
    )
    ai_model: str = Field(
        default="gemini-3.6-flash",
        alias="ZEN_AI_MODEL",
        description="Model name to use for the selected provider",
    )
    temperature: float = Field(
        default=0.7,
        alias="ZEN_AI_TEMPERATURE",
        description="Sampling temperature",
    )

    # API Keys
    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    groq_api_key: str | None = Field(default=None, alias="GROQ_API_KEY")

    # Local Ollama Settings
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="qwen2.5-coder:7b", alias="OLLAMA_MODEL")

    # Voice Configuration
    voice_enabled: bool = Field(default=True, alias="ZEN_VOICE_ENABLED")
    voice_engine: Literal["edge_tts", "sapi", "cloud"] = Field(
        default="edge_tts",
        alias="ZEN_VOICE_ENGINE",
    )
    voice_name: str = Field(default="en-US-GuyNeural", alias="ZEN_VOICE_NAME")
    voice_speed: str = Field(default="+0%", alias="ZEN_VOICE_SPEED")
    wake_word_enabled: bool = Field(default=False, alias="ZEN_WAKE_WORD_ENABLED")
    wake_phrase: str = Field(default="hey zen", alias="ZEN_WAKE_PHRASE")

    # System & Safety Control
    confirmation_required: bool = Field(default=True, alias="ZEN_CONFIRMATION_REQUIRED")
    auto_open_vscode: bool = Field(default=True, alias="ZEN_AUTO_OPEN_VSCODE")
    max_coding_iterations: int = Field(default=5, alias="ZEN_MAX_CODING_ITERATIONS")
    workspace_path: Path = Field(default=WORKSPACE_DIR, alias="ZEN_WORKSPACE_DIR")
    data_path: Path = Field(default=DATA_DIR, alias="ZEN_DATA_DIR")
    log_level: str = Field(default="INFO", alias="ZEN_LOG_LEVEL")

    def ensure_directories(self) -> None:
        """Ensure necessary runtime directories exist."""
        self.workspace_path.mkdir(parents=True, exist_ok=True)
        self.data_path.mkdir(parents=True, exist_ok=True)
        (self.data_path / "cache").mkdir(parents=True, exist_ok=True)


@lru_cache()
def get_settings() -> Settings:
    """Singleton getter for configuration settings."""
    settings = Settings()
    settings.ensure_directories()
    return settings
