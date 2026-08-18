"""
Text Utilities for ZEN Voice Subsystem.

Provides helpers to sanitize text for spoken delivery — e.g., stripping
Markdown syntax that would sound nonsensical when read aloud by a TTS engine.
"""

import re


def strip_markdown_for_tts(text: str) -> str:
    """
    Remove Markdown formatting from text before passing it to a TTS engine.

    Strips: fenced code blocks, inline code, bold/italic, headings,
    links, images, blockquotes, horizontal rules, and bullet/numbered list markers.

    Args:
        text: Raw Markdown string (e.g., an LLM response).

    Returns:
        Plain-text string suitable for spoken delivery.
    """
    if not text:
        return text

    # Remove fenced code blocks (``` ... ```) — replace with brief label
    text = re.sub(r"```[\s\S]*?```", "[code block]", text)

    # Remove inline code (`code`)
    text = re.sub(r"`[^`]+`", "", text)

    # Remove image syntax: ![alt](url)
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)

    # Remove hyperlink syntax: [text](url) → keep the display text
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)

    # Remove bold+italic: ***text*** or ___text___
    text = re.sub(r"\*{3}(.+?)\*{3}", r"\1", text)
    text = re.sub(r"_{3}(.+?)_{3}", r"\1", text)

    # Remove bold: **text** or __text__
    text = re.sub(r"\*{2}(.+?)\*{2}", r"\1", text)
    text = re.sub(r"_{2}(.+?)_{2}", r"\1", text)

    # Remove italic: *text* or _text_
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"_(.+?)_", r"\1", text)

    # Remove ATX headings: ## Heading → Heading
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)

    # Remove blockquote markers: > text → text
    text = re.sub(r"^>\s?", "", text, flags=re.MULTILINE)

    # Remove horizontal rules: ---, ***, ___
    text = re.sub(r"^\s*[-*_]{3,}\s*$", "", text, flags=re.MULTILINE)

    # Remove bullet list markers: - item, * item, + item
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)

    # Remove numbered list markers: 1. item
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)

    # Collapse multiple blank lines into a single one
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()
