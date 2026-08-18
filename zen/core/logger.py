"""
Structured logging module for ZEN with secret masking and Rich console formatting.
"""

import logging
import re
import sys
from pathlib import Path
from rich.console import Console
from rich.logging import RichHandler

console = Console()

# Patterns for masking sensitive information in logs
SECRET_PATTERNS = [
    re.compile(r"(AIza[0-9A-Za-z-_]{35})"),                      # Google API Key
    re.compile(r"(sk-[a-zA-Z0-9]{20,})"),                        # OpenAI API Key
    re.compile(r"(sk-ant-[a-zA-Z0-9-_]{20,})"),                  # Anthropic API Key
    re.compile(r"(gsk_[a-zA-Z0-9]{20,})"),                       # Groq API Key
    re.compile(r"(password|secret|token|api_key)=['\"]?[^'\"]+"), # Common key-value secrets
]


class SecretMaskingFilter(logging.Filter):
    """Filters log records to mask potential API keys and secrets."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self.mask_secrets(record.msg)
        if record.args:
            if isinstance(record.args, tuple):
                record.args = tuple(
                    self.mask_secrets(str(arg)) if isinstance(arg, str) else arg
                    for arg in record.args
                )
            elif isinstance(record.args, dict):
                record.args = {
                    k: self.mask_secrets(str(v)) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
        return True

    @staticmethod
    def mask_secrets(text: str) -> str:
        masked = text
        for pattern in SECRET_PATTERNS:
            masked = pattern.sub("[REDACTED_SECRET]", masked)
        return masked


def setup_logger(
    name: str = "zen",
    log_level: str = "INFO",
    log_file: Path | None = None,
) -> logging.Logger:
    """Configures and returns a logger instance with Rich formatting."""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    logger.propagate = False

    # Clear existing handlers
    if logger.handlers:
        logger.handlers.clear()

    # Secret masking filter
    masking_filter = SecretMaskingFilter()
    logger.addFilter(masking_filter)

    # Console Handler (Rich)
    rich_handler = RichHandler(
        console=console,
        show_time=True,
        show_path=False,
        rich_tracebacks=True,
        tracebacks_show_locals=False,
        markup=True,
    )
    rich_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    rich_handler.addFilter(masking_filter)
    logger.addHandler(rich_handler)

    # Optional File Handler
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
        file_formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(logging.DEBUG)
        file_handler.addFilter(masking_filter)
        logger.addHandler(file_handler)

    return logger


# Default logger instance
logger = setup_logger()
