"""Web page crawler with AI-powered structure analysis."""

from datetime import datetime
from urllib.parse import urljoin

import structlog
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from ..base import BaseCrawler, CrawlerConfig, CrawlResult

logger = structlog.get_logger()


class WebNewsCrawler(BaseCrawler):
    """
    Generic web crawler for news/article pages.

    Features:
    - CSS selector-based extraction
    - Automatic URL resolution
    - AI-powered self-healing when selectors fail
    """

    def __init__(
        self,
        source_id: str,
        url: str,
        config: CrawlerConfig | None = None,
        **kwargs,
    ):
        super().__init__(source_id, url, config, **kwargs)

        # Set default config if not provided
        if not self.config.base_url:
            from urllib.parse import urlparse

            parsed = urlparse(url)
            self.config.base_url = f"{parsed.scheme}://{parsed.netloc}"

    async def parse(self, html: str) -> list[CrawlResult]:
        """Parse HTML and extract article list."""
        results: list[CrawlResult] = []
        soup = BeautifulSoup(html, "lxml")

        # Find list items
        if not self.config.list_selector:
            logger.warning(
                "web_crawler_no_list_selector",
                source_id=self.source_id,
            )
            return results

        items = soup.select(self.config.list_selector)

        if not items:
            logger.warning(
                "web_crawler_no_items_found",
                source_id=self.source_id,
                selector=self.config.list_selector,
            )
            return results

        for item in items:
            try:
                result = self._parse_item(item)
                if result:
                    results.append(result)
            except Exception as e:
                logger.warning(
                    "web_crawler_item_parse_failed",
                    source_id=self.source_id,
                    error=str(e),
                )

        logger.info(
            "web_crawler_parse_success",
            source_id=self.source_id,
            total_items=len(items),
            parsed_items=len(results),
        )

        return results

    def _parse_item(self, item: BeautifulSoup) -> CrawlResult | None:
        """Parse a single list item."""
        # Extract title
        title = None
        if self.config.title_selector:
            title_elem = item.select_one(self.config.title_selector)
            if title_elem:
                title = title_elem.get_text(strip=True)

        if not title:
            return None

        # Extract URL
        url = None
        if self.config.link_selector:
            link_elem = item.select_one(self.config.link_selector)
            if link_elem:
                href = link_elem.get("href")
                if href:
                    url = urljoin(self.config.base_url or self.url, href)

        if not url:
            # Try to find any link in the item
            link_elem = item.select_one("a[href]")
            if link_elem:
                href = link_elem.get("href")
                if href:
                    url = urljoin(self.config.base_url or self.url, href)

        if not url:
            return None

        # Extract content/summary
        content = None
        if self.config.content_selector:
            content_elem = item.select_one(self.config.content_selector)
            if content_elem:
                content = content_elem.get_text(strip=True)

        # Extract date
        published_at = None
        if self.config.date_selector:
            date_elem = item.select_one(self.config.date_selector)
            if date_elem:
                date_str = date_elem.get_text(strip=True)
                # Also check for datetime attribute
                if date_elem.has_attr("datetime"):
                    date_str = date_elem["datetime"]

                try:
                    published_at = date_parser.parse(date_str, fuzzy=True)
                except Exception:
                    pass

        return CrawlResult(
            url=url,
            title=title,
            content=content,
            published_at=published_at,
        )

    async def analyze_and_configure(self) -> CrawlerConfig:
        """
        Use AI to analyze the page and generate crawler configuration.

        This is useful when setting up a new source or when the page structure changes.
        """
        logger.info("web_crawler_analyze_start", source_id=self.source_id, url=self.url)

        html = await self.fetch()
        new_config = await self._attempt_self_heal()

        if new_config:
            self.config = new_config
            logger.info(
                "web_crawler_analyze_success",
                source_id=self.source_id,
                config=vars(new_config),
            )
            return new_config

        raise RuntimeError(f"Failed to analyze page structure for {self.url}")


# Pre-configured web sources for AI news
AI_NEWS_WEB_SOURCES = [
    {
        "name": "AI타임스",
        "url": "https://www.aitimes.com/news/articleList.html?sc_section_code=S1N1",
        "config": CrawlerConfig(
            list_selector=".article-list li",
            title_selector=".titles a",
            link_selector=".titles a",
            date_selector=".byline em",
        ),
    },
    {
        "name": "인공지능신문",
        "url": "https://www.aitimes.kr/news/articleList.html",
        "config": CrawlerConfig(
            list_selector=".article-list li",
            title_selector=".titles a",
            link_selector=".titles a",
            date_selector=".byline em",
        ),
    },
]
