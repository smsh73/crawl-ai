"""Base crawler class with self-healing capabilities."""

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from src.core.ai_orchestrator import AIOrchestrator, AITaskType
from src.core.config import settings

logger = structlog.get_logger()


@dataclass
class CrawlResult:
    """Result of a crawl operation."""

    url: str
    title: str
    content: str | None = None
    published_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def content_hash(self) -> str:
        """Generate hash for deduplication."""
        content = f"{self.url}{self.title}{self.content or ''}"
        return hashlib.sha256(content.encode()).hexdigest()


@dataclass
class CrawlerConfig:
    """Configuration for a crawler."""

    # Selectors (CSS or XPath)
    title_selector: str | None = None
    content_selector: str | None = None
    link_selector: str | None = None
    date_selector: str | None = None
    list_selector: str | None = None

    # Request settings
    headers: dict[str, str] = field(default_factory=dict)
    timeout: int = 30
    use_browser: bool = False

    # Parsing settings
    date_format: str | None = None
    base_url: str | None = None


class BaseCrawler(ABC):
    """
    Abstract base crawler with self-healing capabilities.

    Features:
    - Automatic retry on failure
    - AI-powered structure analysis for self-healing
    - Configurable via database or AI-generated config
    """

    def __init__(
        self,
        source_id: str,
        url: str,
        config: CrawlerConfig | None = None,
        ai_orchestrator: AIOrchestrator | None = None,
    ):
        self.source_id = source_id
        self.url = url
        self.config = config or CrawlerConfig()
        self.ai = ai_orchestrator or AIOrchestrator()
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.config.timeout,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    **self.config.headers,
                },
                follow_redirects=True,
            )
        return self._client

    @retry(
        stop=stop_after_attempt(settings.crawler_max_retries),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def fetch(self, url: str | None = None) -> str:
        """Fetch HTML content from URL."""
        target_url = url or self.url
        client = await self._get_client()

        logger.info("crawler_fetch_start", url=target_url, source_id=self.source_id)

        response = await client.get(target_url)
        response.raise_for_status()

        logger.info(
            "crawler_fetch_success",
            url=target_url,
            status_code=response.status_code,
            content_length=len(response.text),
        )

        return response.text

    @abstractmethod
    async def parse(self, html: str) -> list[CrawlResult]:
        """Parse HTML and extract content. Must be implemented by subclasses."""
        pass

    async def crawl(self) -> list[CrawlResult]:
        """
        Execute the crawl operation.

        Returns:
            List of CrawlResult objects
        """
        try:
            html = await self.fetch()
            results = await self.parse(html)

            logger.info(
                "crawler_crawl_success",
                source_id=self.source_id,
                results_count=len(results),
            )

            return results

        except Exception as e:
            logger.error(
                "crawler_crawl_failed",
                source_id=self.source_id,
                error=str(e),
            )

            # Attempt self-healing if parsing failed
            if "parse" in str(e).lower() or len(await self.parse("")) == 0:
                await self._attempt_self_heal()

            raise

    async def _attempt_self_heal(self) -> CrawlerConfig | None:
        """
        Use AI to analyze page structure and generate new config.

        Returns:
            New CrawlerConfig if successful, None otherwise
        """
        logger.info("crawler_self_heal_start", source_id=self.source_id)

        try:
            html = await self.fetch()

            # Truncate HTML for AI analysis
            html_sample = html[:10000] if len(html) > 10000 else html

            prompt = f"""Analyze this HTML and provide CSS selectors to extract news/article list items.

HTML:
{html_sample}

Return a JSON object with these fields:
- list_selector: CSS selector for the list container or repeated items
- title_selector: CSS selector for article title (relative to list item)
- link_selector: CSS selector for article link (relative to list item)
- date_selector: CSS selector for publish date (relative to list item, if available)
- content_selector: CSS selector for article content/summary (relative to list item, if available)

Only return valid JSON, no explanation."""

            response = await self.ai.request(
                prompt,
                task_type=AITaskType.EXTRACT,
            )

            import json

            config_dict = json.loads(response.content)

            new_config = CrawlerConfig(
                list_selector=config_dict.get("list_selector"),
                title_selector=config_dict.get("title_selector"),
                link_selector=config_dict.get("link_selector"),
                date_selector=config_dict.get("date_selector"),
                content_selector=config_dict.get("content_selector"),
            )

            logger.info(
                "crawler_self_heal_success",
                source_id=self.source_id,
                new_config=config_dict,
            )

            return new_config

        except Exception as e:
            logger.error(
                "crawler_self_heal_failed",
                source_id=self.source_id,
                error=str(e),
            )
            return None

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
