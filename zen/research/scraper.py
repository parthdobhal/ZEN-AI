"""
Async Web Content Fetcher and Text Extractor.
"""

from bs4 import BeautifulSoup
import httpx
from zen.core.logger import logger


class WebScraper:
    """Fetches web pages asynchronously and extracts clean article text."""

    def __init__(self, timeout: float = 12.0) -> None:
        self.timeout = timeout
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36 ZEN/0.1"
            )
        }

    async def fetch_and_extract(self, url: str, max_chars: int = 4000) -> str:
        """Fetches page content, strips boilerplate HTML, and returns clean text."""
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                headers=self.headers,
                follow_redirects=True,
            ) as client:
                res = await client.get(url)
                if res.status_code != 200:
                    return f"[HTTP {res.status_code} Error retrieving page]"

                html_content = res.text
                soup = BeautifulSoup(html_content, "html.parser")

                # Remove non-content elements
                for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "aside", "svg"]):
                    tag.decompose()

                # Extract text
                text = soup.get_text(separator=" ", strip=True)
                # Collapse excess whitespace
                cleaned = " ".join(text.split())
                return cleaned[:max_chars]
        except Exception as e:
            logger.debug(f"Failed to scrape {url}: {e}")
            return f"[Failed to load content from {url}: {e}]"
