"""
DuckDuckGo Search Backend Provider.
"""

from typing import Any
from ddgs import DDGS
from zen.core.logger import logger


class DuckDuckGoProvider:
    """Queries DuckDuckGo for web and news search results."""

    def __init__(self) -> None:
        self.ddgs = DDGS()

    def search(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        """Synchronous search wrapper (can be run in thread executor)."""
        try:
            results = list(self.ddgs.text(query, max_results=max_results))
            formatted = []
            for r in results:
                formatted.append(
                    {
                        "title": r.get("title", ""),
                        "url": r.get("href", ""),
                        "snippet": r.get("body", ""),
                    }
                )
            return formatted
        except Exception as e:
            logger.error(f"DuckDuckGo search error for '{query}': {e}")
            return []
