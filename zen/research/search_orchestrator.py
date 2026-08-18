"""
Web Research Orchestrator and Tools for ZEN.
"""

import asyncio
from typing import Any
from pydantic import BaseModel, Field

from zen.config.constants import RISK_READ_ONLY
from zen.core.logger import logger
from zen.research.providers.ddg_search import DuckDuckGoProvider
from zen.research.scraper import WebScraper
from zen.tools.base import BaseTool, ToolResult


class WebSearchParams(BaseModel):
    query: str = Field(description="Search query to find current web information")
    max_results: int = Field(default=5, ge=1, le=10, description="Number of results to retrieve")


class DeepResearchParams(BaseModel):
    query: str = Field(description="Topic or question requiring multi-source in-depth research")
    num_sources: int = Field(default=3, ge=1, le=5, description="Number of top web sources to fetch and scrape")


class WebSearchTool(BaseTool):
    """Searches the internet for real-time information."""

    name = "web_search"
    description = "Searches the internet using DuckDuckGo to find real-time, current information, news, or technical documentation."
    risk_level = RISK_READ_ONLY
    parameters_schema = WebSearchParams

    def __init__(self) -> None:
        self.ddg = DuckDuckGoProvider()

    async def execute(self, params: WebSearchParams, context: Any = None) -> ToolResult:
        try:
            # Run blocking search in thread executor
            results = await asyncio.to_thread(self.ddg.search, params.query, params.max_results)
            if not results:
                return ToolResult.ok(data=[], message=f"No search results found for '{params.query}'.")

            summary_lines = [f"Search results for '{params.query}':\n"]
            for i, r in enumerate(results, 1):
                summary_lines.append(f"[{i}] {r['title']}")
                summary_lines.append(f"    URL: {r['url']}")
                summary_lines.append(f"    Snippet: {r['snippet']}\n")

            return ToolResult.ok(data=results, message="\n".join(summary_lines))
        except Exception as e:
            return ToolResult.fail(f"Search failed: {e}")


class DeepResearchTool(BaseTool):
    """Performs multi-source deep research by querying and scraping top search results."""

    name = "deep_research"
    description = "Searches multiple sources on the web, scrapes the full article text from the best pages, and compiles cited findings."
    risk_level = RISK_READ_ONLY
    parameters_schema = DeepResearchParams

    def __init__(self) -> None:
        self.ddg = DuckDuckGoProvider()
        self.scraper = WebScraper()

    async def execute(self, params: DeepResearchParams, context: Any = None) -> ToolResult:
        try:
            # 1. Search for top URLs
            results = await asyncio.to_thread(self.ddg.search, params.query, max_results=params.num_sources)
            if not results:
                return ToolResult.ok(message=f"No research sources found for '{params.query}'.")

            # 2. Fetch page contents in parallel
            scrape_tasks = [self.scraper.fetch_and_extract(r["url"]) for r in results]
            contents = await asyncio.gather(*scrape_tasks, return_exceptions=True)

            compiled_sources = []
            output_blocks = [f"### Multi-Source Research on: {params.query}\n"]

            for i, (res, content) in enumerate(zip(results, contents), 1):
                page_text = content if isinstance(content, str) else "[Failed to fetch]"
                source_entry = {
                    "source_id": i,
                    "title": res["title"],
                    "url": res["url"],
                    "content_preview": page_text[:1500],
                }
                compiled_sources.append(source_entry)

                output_blocks.append(f"#### Source [{i}]: {res['title']}")
                output_blocks.append(f"**URL**: {res['url']}")
                output_blocks.append(f"**Excerpt**: {page_text[:1200]}...\n")

            return ToolResult.ok(data=compiled_sources, message="\n".join(output_blocks))
        except Exception as e:
            return ToolResult.fail(f"Deep research failed: {e}")
