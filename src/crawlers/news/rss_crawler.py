"""RSS Feed Crawler."""

from datetime import datetime
from typing import Any

import feedparser
import structlog
from dateutil import parser as date_parser

from ..base import BaseCrawler, CrawlerConfig, CrawlResult

logger = structlog.get_logger()


class RSSCrawler(BaseCrawler):
    """
    Crawler for RSS/Atom feeds.

    Supports:
    - Standard RSS 2.0
    - Atom feeds
    - Automatic date parsing
    """

    async def fetch(self, url: str | None = None) -> str:
        """Fetch RSS feed content."""
        return await super().fetch(url)

    async def parse(self, html: str) -> list[CrawlResult]:
        """Parse RSS feed and extract entries."""
        results: list[CrawlResult] = []

        try:
            feed = feedparser.parse(html)

            if feed.bozo and not feed.entries:
                logger.warning(
                    "rss_parse_warning",
                    source_id=self.source_id,
                    error=str(feed.bozo_exception) if feed.bozo_exception else "Unknown",
                )

            for entry in feed.entries:
                try:
                    result = self._parse_entry(entry)
                    if result:
                        results.append(result)
                except Exception as e:
                    logger.warning(
                        "rss_entry_parse_failed",
                        source_id=self.source_id,
                        entry_title=getattr(entry, "title", "Unknown"),
                        error=str(e),
                    )

            logger.info(
                "rss_parse_success",
                source_id=self.source_id,
                total_entries=len(feed.entries),
                parsed_entries=len(results),
            )

        except Exception as e:
            logger.error(
                "rss_parse_failed",
                source_id=self.source_id,
                error=str(e),
            )
            raise

        return results

    def _parse_entry(self, entry: Any) -> CrawlResult | None:
        """Parse a single RSS entry."""
        # Get URL
        url = getattr(entry, "link", None)
        if not url:
            return None

        # Get title
        title = getattr(entry, "title", "")
        if not title:
            return None

        # Get content
        content = None
        if hasattr(entry, "content") and entry.content:
            content = entry.content[0].get("value", "")
        elif hasattr(entry, "summary"):
            content = entry.summary
        elif hasattr(entry, "description"):
            content = entry.description

        # Get published date
        published_at = None
        date_fields = ["published_parsed", "updated_parsed", "created_parsed"]
        for field in date_fields:
            if hasattr(entry, field) and getattr(entry, field):
                try:
                    time_tuple = getattr(entry, field)
                    published_at = datetime(*time_tuple[:6])
                    break
                except Exception:
                    pass

        # Fallback: try parsing string date
        if not published_at:
            date_str_fields = ["published", "updated", "created"]
            for field in date_str_fields:
                if hasattr(entry, field) and getattr(entry, field):
                    try:
                        published_at = date_parser.parse(getattr(entry, field))
                        break
                    except Exception:
                        pass

        # Build metadata
        metadata: dict[str, Any] = {}

        if hasattr(entry, "author"):
            metadata["author"] = entry.author

        if hasattr(entry, "tags"):
            metadata["tags"] = [tag.term for tag in entry.tags if hasattr(tag, "term")]

        if hasattr(entry, "id"):
            metadata["entry_id"] = entry.id

        return CrawlResult(
            url=url,
            title=title,
            content=content,
            published_at=published_at,
            metadata=metadata,
        )


# Pre-configured RSS sources for AI news
AI_NEWS_RSS_SOURCES = [
    {
        "name": "TechCrunch AI",
        "url": "https://techcrunch.com/category/artificial-intelligence/feed/",
    },
    {
        "name": "VentureBeat AI",
        "url": "https://venturebeat.com/category/ai/feed/",
    },
    {
        "name": "MIT Technology Review AI",
        "url": "https://www.technologyreview.com/topic/artificial-intelligence/feed",
    },
    {
        "name": "The Verge AI",
        "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    },
    {
        "name": "Wired AI",
        "url": "https://www.wired.com/feed/tag/ai/latest/rss",
    },
    {
        "name": "Ars Technica AI",
        "url": "https://feeds.arstechnica.com/arstechnica/technology-lab",
    },
    {
        "name": "Google AI Blog",
        "url": "https://blog.google/technology/ai/rss/",
    },
    {
        "name": "OpenAI Blog",
        "url": "https://openai.com/blog/rss/",
    },
    {
        "name": "Anthropic News",
        "url": "https://www.anthropic.com/news/rss",
    },
    {
        "name": "Hugging Face Blog",
        "url": "https://huggingface.co/blog/feed.xml",
    },
]
