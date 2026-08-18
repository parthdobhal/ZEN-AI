"""
ZEN Web Intelligence & Research Subsystem
"""

from zen.research.providers.ddg_search import DuckDuckGoProvider
from zen.research.scraper import WebScraper
from zen.research.search_orchestrator import WebSearchTool, DeepResearchTool
from zen.tools.registry import ToolRegistry


def register_research_tools(registry: ToolRegistry) -> None:
    """Register web research tools with the tool registry."""
    registry.register(WebSearchTool())
    registry.register(DeepResearchTool())


__all__ = [
    "DuckDuckGoProvider",
    "WebScraper",
    "WebSearchTool",
    "DeepResearchTool",
    "register_research_tools",
]
